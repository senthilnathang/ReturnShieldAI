from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from uuid import UUID

import numpy as np

from backend.app.core.redis import RedisClient, redis_client

from .config import ml_config
from .data_loader import MLDataLoader
from .model_registry import load_best_model
from .predictor import MLModelPredictor
from .schemas import PredictionResponse


class MLInferenceService:
    def __init__(self, session, redis: RedisClient | None = None):
        self.session = session
        self.redis = redis or redis_client
        self._predictor: MLModelPredictor | None = None

    async def _get_predictor(self, model_type: str | None = None, model_version: str | None = None) -> MLModelPredictor | None:
        try:
            if model_type:
                return MLModelPredictor.load(model_type=model_type, version=model_version)
            if self._predictor is None:
                self._predictor = MLModelPredictor.load()
            return self._predictor
        except Exception:
            return None

    async def best_model_metadata(self) -> dict[str, Any] | None:
        try:
            cached = await self.redis.cache_get_json("ml:best_model:metadata")
            if cached:
                return cached
        except Exception:
            pass
        try:
            bundle = load_best_model()
        except Exception:
            return None
        metadata = bundle["metadata"]
        try:
            await self.redis.cache_set_json("ml:best_model:metadata", metadata, ttl=ml_config.metadata_ttl_seconds)
        except Exception:
            pass
        return metadata

    def _fallback_probability(self, row: dict[str, Any]) -> float:
        score = 0.15
        score += 0.10 if float(row.get("weight_difference", 0) or 0) > 0.2 else 0.0
        score += 0.12 if float(row.get("hours_after_delivery", 999) or 999) < 48 else 0.0
        score += 0.18 if float(row.get("chargeback_count", 0) or 0) > 0 else 0.0
        score += 0.10 if float(row.get("same_address_customer_count", 0) or 0) > 1 else 0.0
        score += 0.08 if float(row.get("same_payment_token_count", 0) or 0) > 1 else 0.0
        score += 0.07 if float(row.get("has_empty_box_claim", 0) or 0) > 0 else 0.0
        score += 0.07 if float(row.get("has_urgent_refund_language", 0) or 0) > 0 else 0.0
        return float(max(0.01, min(0.95, score)))

    async def predict_return(self, return_id: UUID, model_type: str | None = None, model_version: str | None = None) -> PredictionResponse:
        start = time.perf_counter()
        cache_key = f"ml:prediction:{return_id}:{model_version or model_type or 'best'}"
        try:
            cached = await self.redis.cache_get_json(cache_key)
            if cached:
                cached["cached"] = True
                return PredictionResponse(**cached)
        except Exception:
            pass

        loader = MLDataLoader(self.session)
        frame = await loader.load_prediction_frame(return_id)
        if frame.empty:
            raise ValueError(f"Return {return_id} not found")
        row = frame.iloc[0].to_dict()

        predictor = await self._get_predictor(model_type, model_version)
        if predictor is None:
            prob = self._fallback_probability(row)
            score = int(round(prob * 100))
            risk = "HIGH" if prob >= 0.75 else "MEDIUM" if prob >= 0.40 else "LOW"
            response = PredictionResponse(
                return_id=str(return_id),
                model_type=model_type or "rule_fallback",
                model_version=model_version or "fallback",
                fraud_probability=prob,
                ml_score=score,
                risk_level=risk,
                top_features=[],
                latency_ms=int((time.perf_counter() - start) * 1000),
                fallback_used=True,
            )
            try:
                await self.redis.cache_set_json(cache_key, response.model_dump(), ttl=ml_config.prediction_ttl_seconds)
            except Exception:
                pass
            return response

        prediction = predictor.predict_frame(frame, original_row=row)
        latency_ms = int((time.perf_counter() - start) * 1000)
        response = PredictionResponse(
            return_id=str(return_id),
            model_type=prediction["model_type"],
            model_version=prediction["model_version"],
            fraud_probability=float(prediction["fraud_probability"]),
            ml_score=int(prediction["ml_score"]),
            risk_level=prediction["risk_level"],
            top_features=prediction["top_features"],
            latency_ms=latency_ms,
        )
        try:
            await self.redis.cache_set_json(cache_key, response.model_dump(), ttl=ml_config.prediction_ttl_seconds)
        except Exception:
            pass
        return response

    async def predict_batch(self, return_ids: list[UUID], model_type: str | None = None, model_version: str | None = None) -> list[PredictionResponse]:
        return [await self.predict_return(return_id, model_type, model_version) for return_id in return_ids]

    @staticmethod
    def heuristic_from_row(row: dict[str, Any]) -> float:
        score = 0.15
        score += 0.10 if float(row.get("weight_difference", 0) or 0) > 0.2 else 0.0
        score += 0.12 if float(row.get("hours_after_delivery", 999) or 999) < 48 else 0.0
        score += 0.18 if float(row.get("chargeback_count", 0) or 0) > 0 else 0.0
        score += 0.10 if float(row.get("same_address_customer_count", 0) or 0) > 1 else 0.0
        score += 0.08 if float(row.get("same_payment_token_count", 0) or 0) > 1 else 0.0
        score += 0.07 if float(row.get("has_empty_box_claim", 0) or 0) > 0 else 0.0
        score += 0.07 if float(row.get("has_urgent_refund_language", 0) or 0) > 0 else 0.0
        return float(max(0.01, min(0.95, score)))
