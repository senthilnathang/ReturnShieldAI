from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "merchants"

DEFAULT_MERCHANT_CONFIG = {
    "allowed_return_rate": 0.10,
    "high_risk_categories": ["electronics", "jewelry", "apparel"],
    "risk_thresholds": {"low": 40, "medium": 70},
    "fusion_weights": {"rule_score": 0.25, "structured_ml_score": 0.25, "nlp_score": 0.20, "anomaly_score": 0.15, "graph_risk_score": 0.10, "customer_risk_score": 0.05},
    "rules": {"enable_weight_mismatch": True, "enable_fast_return": True},
    "models": {"structured_ml": "default", "nlp": "default"},
}


class MerchantEngine:
    def __init__(self, config_dir: str | Path = CONFIG_DIR):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, Any]] = {}

    def get_config(self, merchant_id: str) -> dict[str, Any]:
        if merchant_id in self._cache:
            return self._cache[merchant_id]
        config = self._load_config(merchant_id)
        self._cache[merchant_id] = config
        return config

    def _load_config(self, merchant_id: str) -> dict[str, Any]:
        config_path = self.config_dir / f"{merchant_id}.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return {**DEFAULT_MERCHANT_CONFIG, **yaml.safe_load(f)}
        return dict(DEFAULT_MERCHANT_CONFIG)

    def save_config(self, merchant_id: str, config: dict[str, Any]) -> None:
        merged = {**DEFAULT_MERCHANT_CONFIG, **config}
        config_path = self.config_dir / f"{merchant_id}.yaml"
        with open(config_path, "w") as f:
            yaml.dump(merged, f, default_flow_style=False)
        self._cache[merchant_id] = merged

    def list_merchants(self) -> list[str]:
        return sorted(f.stem for f in self.config_dir.glob("*.yaml"))

    def get_thresholds(self, merchant_id: str) -> dict[str, float]:
        config = self.get_config(merchant_id)
        return config.get("risk_thresholds", DEFAULT_MERCHANT_CONFIG["risk_thresholds"])

    def get_fusion_weights(self, merchant_id: str) -> dict[str, float]:
        config = self.get_config(merchant_id)
        return config.get("fusion_weights", DEFAULT_MERCHANT_CONFIG["fusion_weights"])

    def is_high_risk_category(self, merchant_id: str, category: str) -> bool:
        config = self.get_config(merchant_id)
        return category.lower() in [c.lower() for c in config.get("high_risk_categories", [])]
