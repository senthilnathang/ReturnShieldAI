from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class MLConfig:
    artifact_root: Path = Path(__file__).resolve().parents[3] / "models"
    train_stream: str = "ml:train:stream"
    prediction_ttl_seconds: int = 600
    metadata_ttl_seconds: int = 300
    default_threshold: float = 0.5
    high_risk_threshold: float = 0.75
    manual_review_threshold: float = 0.40
    random_state: int = 42
    max_training_rows: int | None = None
    version_prefix: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @property
    def best_model_dir(self) -> Path:
        return self.artifact_root / "best_model"


ml_config = MLConfig()
