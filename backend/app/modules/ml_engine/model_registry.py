from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.prod_models.model_training_run import ModelTrainingRun

from .config import ml_config

try:
    import torch
except Exception:  # pragma: no cover - optional dependency
    torch = None


@dataclass
class ArtifactInfo:
    model_type: str
    version: str
    artifact_dir: str
    artifact_path: str
    preprocessor_path: str
    metadata_path: str
    metrics_path: str
    metadata: dict[str, Any]
    metrics: dict[str, Any]


def artifact_root() -> Path:
    ml_config.artifact_root.mkdir(parents=True, exist_ok=True)
    return ml_config.artifact_root


def model_dir(model_type: str, version: str) -> Path:
    return artifact_root() / model_type / version


def next_version(model_type: str) -> str:
    prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = artifact_root() / model_type
    base.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.name for p in base.iterdir() if p.is_dir() and p.name.startswith(prefix))
    return f"{prefix}-{len(existing) + 1:03d}"


def save_model(model, preprocessor, metadata: dict[str, Any], model_type: str, metrics: Optional[dict[str, Any]] = None) -> ArtifactInfo:
    version = metadata.get("version") or next_version(model_type)
    metadata = dict(metadata)
    metadata.update({
        "version": version,
        "model_type": model_type,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    })
    metrics = dict(metrics or metadata.get("metrics", {}))
    metadata["metrics"] = metrics

    output_dir = model_dir(model_type, version)
    output_dir.mkdir(parents=True, exist_ok=True)

    artifact_format = metadata.get("artifact_format", "pkl")
    if artifact_format == "torch" and torch is not None:
        artifact_path = output_dir / "model.pt"
        torch.save({"state_dict": model.state_dict(), "model_config": metadata.get("model_config", {})}, artifact_path)
    else:
        artifact_path = output_dir / "model.pkl"
        joblib.dump(model, artifact_path)
        metadata["artifact_format"] = "pkl"

    preprocessor_path = output_dir / "preprocessor.pkl"
    joblib.dump(preprocessor, preprocessor_path)

    metadata_path = output_dir / "metadata.json"
    metrics_path = output_dir / "metrics.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str))
    metrics_path.write_text(json.dumps(metrics, indent=2, default=str))

    return ArtifactInfo(
        model_type=model_type,
        version=version,
        artifact_dir=str(output_dir),
        artifact_path=str(artifact_path),
        preprocessor_path=str(preprocessor_path),
        metadata_path=str(metadata_path),
        metrics_path=str(metrics_path),
        metadata=metadata,
        metrics=metrics,
    )


def _load_metadata(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def _load_from_dir(output_dir: Path) -> dict[str, Any]:
    metadata = _load_metadata(output_dir / "metadata.json")
    metrics = _load_metadata(output_dir / "metrics.json")
    if not metadata:
        raise FileNotFoundError(f"Missing metadata in {output_dir}")
    artifact_format = metadata.get("artifact_format", "pkl")
    if artifact_format == "torch" and torch is not None:
        from .trainer_common import FraudNet

        artifact = torch.load(output_dir / "model.pt", map_location="cpu")
        config = artifact.get("model_config", {})
        model = FraudNet(**config)
        model.load_state_dict(artifact["state_dict"])
        model.eval()
    else:
        model = joblib.load(output_dir / "model.pkl")
    preprocessor = joblib.load(output_dir / "preprocessor.pkl")
    return {
        "model": model,
        "preprocessor": preprocessor,
        "metadata": metadata,
        "metrics": metrics,
        "artifact_dir": str(output_dir),
        "artifact_path": str(output_dir / ("model.pt" if artifact_format == "torch" and torch is not None else "model.pkl")),
    }


def load_model(model_type: str, version: str = "latest") -> dict[str, Any]:
    base = artifact_root() / model_type
    if not base.exists():
        raise FileNotFoundError(f"No models for {model_type}")
    if version == "latest":
        versions = sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.name)
        if not versions:
            raise FileNotFoundError(f"No versions for {model_type}")
        output_dir = versions[-1]
    else:
        output_dir = base / version
    return _load_from_dir(output_dir)


def load_best_model() -> dict[str, Any]:
    best_dir = ml_config.best_model_dir
    metadata = _load_metadata(best_dir / "metadata.json")
    if not metadata:
        raise FileNotFoundError("No best model registered")
    model_type = metadata["model_type"]
    version = metadata["version"]
    return load_model(model_type, version)


def list_model_versions() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    root_dir = artifact_root()
    if not root_dir.exists():
        return results
    for model_type_dir in sorted([p for p in root_dir.iterdir() if p.is_dir() and p.name != "best_model"]):
        for version_dir in sorted([p for p in model_type_dir.iterdir() if p.is_dir()]):
            metadata = _load_metadata(version_dir / "metadata.json")
            metrics = _load_metadata(version_dir / "metrics.json")
            if not metadata:
                continue
            results.append({
                "model_name": metadata.get("model_name", model_type_dir.name),
                "model_type": model_type_dir.name,
                "version": version_dir.name,
                "is_best": bool(metadata.get("is_best", False)),
                "artifact_path": str(version_dir),
                "metrics": metrics,
                "metadata": metadata,
                "created_at": metadata.get("saved_at"),
            })
    return results


async def register_training_run(session: AsyncSession, metrics: dict[str, Any]) -> ModelTrainingRun:
    run = ModelTrainingRun(
        model_name=metrics.get("model_name", metrics.get("model_type", "unknown")),
        model_type=metrics.get("model_type", metrics.get("model_name", "unknown")),
        version=metrics["version"],
        accuracy=float(metrics.get("accuracy", 0.0)),
        precision=float(metrics.get("precision", 0.0)),
        recall=float(metrics.get("recall", 0.0)),
        f1=float(metrics.get("f1", 0.0)),
        roc_auc=float(metrics.get("roc_auc", 0.0)),
        pr_auc=float(metrics.get("pr_auc", 0.0)),
        false_positive_rate=float(metrics.get("false_positive_rate", 0.0)),
        false_negative_rate=float(metrics.get("false_negative_rate", 0.0)),
        training_time_seconds=float(metrics.get("training_time_seconds", 0.0)),
        prediction_latency_ms=float(metrics.get("prediction_latency_ms", 0.0)),
        artifact_path=str(metrics.get("artifact_path", "")),
        metrics_json=dict(metrics),
        metadata_json=dict(metrics.get("metadata", {})),
        is_best=bool(metrics.get("is_best", False)),
        promoted_at=datetime.now(timezone.utc) if metrics.get("is_best") else None,
        notes=metrics.get("notes"),
    )
    session.add(run)
    await session.flush()
    return run


def promote_model_to_best(model_type: str, version: str) -> dict[str, Any]:
    source = model_dir(model_type, version)
    if not source.exists():
        raise FileNotFoundError(f"Artifact not found: {source}")
    best_dir = ml_config.best_model_dir
    if best_dir.exists():
        shutil.rmtree(best_dir)
    shutil.copytree(source, best_dir)
    metadata = _load_metadata(best_dir / "metadata.json")
    metrics = _load_metadata(best_dir / "metrics.json")
    metadata.update({
        "best_model_type": model_type,
        "is_best": True,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    })
    (best_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))
    return {"metadata": metadata, "metrics": metrics, "artifact_dir": str(best_dir)}


def rollback_best_model(version: str) -> dict[str, Any]:
    best = load_best_model()
    metadata = best["metadata"]
    return promote_model_to_best(metadata["model_type"], version)
