from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_async_session
from backend.app.core.redis import get_redis, RedisClient
from backend.app.prod_models.model_training_run import ModelTrainingRun

from .model_registry import list_model_versions, load_best_model, load_model, promote_model_to_best
from .inference_service import MLInferenceService
from .schemas import (
    BestModelResponse,
    ModelSummary,
    PredictionBatchRequest,
    PredictionRequest,
    PredictionResponse,
    TrainingComparisonResponse,
    TrainingRequest,
    TrainingRunRead,
)
from .train_all import enqueue_training_job, train_models

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/predict", response_model=PredictionResponse)
async def predict(payload: PredictionRequest, session: AsyncSession = Depends(get_async_session), redis: RedisClient = Depends(get_redis)):
    service = MLInferenceService(session, redis)
    return await service.predict_return(payload.return_id, payload.model_type, payload.model_version)


@router.post("/predict/batch", response_model=list[PredictionResponse])
async def predict_batch(payload: PredictionBatchRequest, session: AsyncSession = Depends(get_async_session), redis: RedisClient = Depends(get_redis)):
    service = MLInferenceService(session, redis)
    return await service.predict_batch(payload.return_ids, payload.model_type, payload.model_version)


@router.post("/train")
async def train(payload: TrainingRequest, session: AsyncSession = Depends(get_async_session), redis: RedisClient = Depends(get_redis)):
    if payload.enqueue_only:
        await enqueue_training_job(redis, {"model_types": json.dumps(payload.model_types or []), "merchant_id": str(payload.merchant_id) if payload.merchant_id else "", "limit": str(payload.limit or ""), "promote_best": "true" if payload.promote_best else "false"})
        return {"queued": True, "stream": "ml:train:stream"}
    return await train_models(session, payload.model_types, payload.merchant_id, payload.limit, payload.promote_best, redis=redis)


@router.get("/models")
async def models() -> list[ModelSummary]:
    models = []
    for item in list_model_versions():
        models.append(ModelSummary(**item))
    return models


@router.get("/models/best", response_model=BestModelResponse)
async def best_model():
    try:
        bundle = load_best_model()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    metadata = bundle["metadata"]
    metrics = bundle.get("metrics", {})
    return BestModelResponse(
        model_name=metadata.get("model_name", metadata.get("model_type", "unknown")),
        model_type=metadata.get("model_type", "unknown"),
        version=metadata.get("version", "unknown"),
        is_best=True,
        artifact_path=bundle["artifact_path"],
        metrics=metrics,
        metadata=metadata,
        created_at=None,
    )


@router.get("/training-runs", response_model=list[TrainingRunRead])
async def training_runs(session: AsyncSession = Depends(get_async_session)):
    stmt = select(ModelTrainingRun).order_by(desc(ModelTrainingRun.created_at))
    rows = (await session.execute(stmt)).scalars().all()
    return rows


@router.post("/models/{model_type}/{version}/promote")
async def promote(model_type: str, version: str, session: AsyncSession = Depends(get_async_session)):
    try:
        result = promote_model_to_best(model_type, version)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.execute(update(ModelTrainingRun).values(is_best=False))
    await session.execute(
        update(ModelTrainingRun)
        .where(ModelTrainingRun.model_type == model_type, ModelTrainingRun.version == version)
        .values(is_best=True)
    )
    await session.commit()
    return result
