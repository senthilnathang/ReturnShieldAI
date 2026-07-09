from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import async_session_factory

from backend.app.core.redis import RedisClient, redis_client
from backend.app.prod_models.model_training_run import ModelTrainingRun

from .config import ml_config
from .data_loader import MLDataLoader
from .model_registry import load_model, promote_model_to_best, register_training_run
from .schemas import TrainingComparisonResponse, TrainingMetric
from .trainer_common import TrainingArtifact, select_best_model, train_single_model

MODEL_TYPES = ["logistic_regression", "random_forest", "xgboost", "neural_network"]


async def train_models(session: AsyncSession, model_types: list[str] | None = None, merchant_id=None, limit: int | None = None, promote_best: bool = True, redis: RedisClient | None = None) -> TrainingComparisonResponse:
    loader = MLDataLoader(session)
    frame = await loader.load_training_frame(merchant_id=merchant_id, limit=limit or ml_config.max_training_rows)
    if frame.empty:
        raise ValueError("No training data available")

    redis = redis or redis_client
    try:
        await redis.publish("ml:training:progress", {"stage": "loaded", "rows": int(len(frame))})
    except Exception:
        pass

    model_types = model_types or MODEL_TYPES
    artifacts: list[TrainingArtifact] = []
    for model_type in model_types:
        try:
            await redis.publish("ml:training:progress", {"stage": "training", "model_type": model_type})
        except Exception:
            pass
        artifact = await asyncio.to_thread(train_single_model, frame, model_type)
        artifacts.append(artifact)
        try:
            await redis.publish("ml:training:progress", {"stage": "trained", "model_type": model_type, "version": artifact.version})
        except Exception:
            pass

    metrics_rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        metrics = dict(artifact.artifact_info.metrics)
        metrics.update({
            "model_name": artifact.model_type,
            "model_type": artifact.model_type,
            "version": artifact.version,
            "artifact_path": artifact.artifact_info.artifact_dir,
            "metadata": artifact.artifact_info.metadata,
        })
        metrics_rows.append(metrics)

    best = select_best_model(metrics_rows)
    if best is not None and promote_best:
        promote_model_to_best(best["model_type"], best["version"])

    # mark best in DB and store training runs
    results: list[TrainingMetric] = []
    for metrics in metrics_rows:
        is_best = bool(best and metrics["model_type"] == best["model_type"] and metrics["version"] == best["version"])
        metrics["is_best"] = is_best
        await register_training_run(session, metrics)
        results.append(TrainingMetric(**{k: v for k, v in metrics.items() if k in TrainingMetric.model_fields}))

    if best is not None:
        await session.execute(update(ModelTrainingRun).values(is_best=False))
        await session.execute(
            update(ModelTrainingRun)
            .where(ModelTrainingRun.model_type == best["model_type"], ModelTrainingRun.version == best["version"])
            .values(is_best=True, promoted_at=datetime.now(timezone.utc))
        )
    await session.commit()

    return TrainingComparisonResponse(
        results=results,
        best_model_type=best["model_type"] if best else None,
        best_version=best["version"] if best else None,
        best_artifact_path=best["artifact_path"] if best else None,
    )


async def train_model(session: AsyncSession, model_type: str, merchant_id=None, limit: int | None = None, promote_best: bool = False, redis: RedisClient | None = None) -> TrainingComparisonResponse:
    return await train_models(session, [model_type], merchant_id=merchant_id, limit=limit, promote_best=promote_best, redis=redis)


async def enqueue_training_job(redis: RedisClient, payload: dict[str, Any]) -> None:
    await redis.stream_add(ml_config.train_stream, payload)


def _parse_model_types(value: str | None) -> list[str] | None:
    if not value:
        return None
    if value == "all":
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


async def _cli_run(args) -> TrainingComparisonResponse:
    async with async_session_factory() as session:
        return await train_models(
            session,
            model_types=_parse_model_types(args.model_types),
            merchant_id=args.merchant_id,
            limit=args.limit,
            promote_best=not args.no_promote,
        )


def main():
    parser = argparse.ArgumentParser(description="Train and compare ReturnShield AI fraud models")
    parser.add_argument("--model-types", default="all", help="Comma-separated model types or 'all'")
    parser.add_argument("--merchant-id", default=None, help="Optional merchant UUID to train on a single merchant")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit")
    parser.add_argument("--no-promote", action="store_true", help="Do not promote the best model")
    args = parser.parse_args()
    result = asyncio.run(_cli_run(args))
    print(json.dumps(result.model_dump(), indent=2, default=str))


if __name__ == "__main__":
    main()
