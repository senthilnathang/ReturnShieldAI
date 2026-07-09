from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .config import nlp_config
from .trainer import train_fraud_classifier, train_intent_classifier

router = APIRouter(prefix="/nlp", tags=["nlp"])

_predictor: NLPredictor | None = None


def get_predictor() -> NLPredictor:
    from .predictor import NLPredictor

    global _predictor
    if _predictor is None:
        _predictor = NLPredictor()
    return _predictor


class SourceText(BaseModel):
    return_reason: Optional[str] = None
    customer_chat: Optional[str] = None
    customer_email: Optional[str] = None
    warehouse_notes: Optional[str] = None
    analyst_notes: Optional[str] = None
    courier_remarks: Optional[str] = None


class PredictRequest(BaseModel):
    sources: SourceText
    return_id: Optional[UUID] = None


class TrainRequest(BaseModel):
    model_type: str = "logistic_regression"
    train_intents: bool = True
    train_fraud: bool = True
    test_size: float = 0.2


class SearchRequest(BaseModel):
    text: str = Field(..., min_length=1)
    k: int = 20
    min_score: float = 0.0


class PredictResponse(BaseModel):
    nlp_score: int
    fraud_probability: float
    risk_level: str
    confidence: float
    detected_patterns: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    explanation: str
    similar_cases: list[dict[str, Any]]
    intents: dict[str, Any]
    sentiment: dict[str, Any]
    toxicity: dict[str, Any]
    keyword_analysis: dict[str, Any]
    entities: dict[str, Any]
    sources_analyzed: list[str]
    latency_ms: int


@router.post("/predict", response_model=PredictResponse)
async def predict(
    payload: PredictRequest,
    predictor: NLPredictor = Depends(get_predictor),
):
    sources = payload.sources.model_dump()
    sources = {k: v for k, v in sources.items() if v}
    if not sources:
        raise HTTPException(status_code=400, detail="At least one text source is required")
    result = predictor.predict(sources)
    return PredictResponse(**result)


@router.post("/predict/text", response_model=PredictResponse)
async def predict_text(
    text: str = Query(..., min_length=1),
    predictor: NLPredictor = Depends(get_predictor),
):
    result = predictor.predict_text(text)
    return PredictResponse(**result)


@router.post("/train")
async def train(
    payload: TrainRequest,
):
    results = {}
    if payload.train_intents:
        from sklearn.datasets import make_multilabel_classification
        from sklearn.feature_extraction.text import CountVectorizer
        import numpy as np

        sample_texts = [
            "the box was empty when i opened it nothing inside",
            "item arrived damaged broken screen not working",
            "i never received my order tracking shows delivered but nothing",
            "i need a refund immediately this is urgent",
            "if you don't refund i will chargeback with my bank",
            "i used the product for my event now returning",
            "missing charger and cables incomplete item",
            "this is fake not authentic counterfeit product",
            "the serial number on the box is different from the device",
            "i want to speak to a manager this is unacceptable",
        ] * 10
        sample_labels = [
            ["empty_box_claim"],
            ["fake_damaged_item"],
            ["item_not_received"],
            ["refund_urgency"],
            ["chargeback_threat"],
            ["return_abuse"],
            ["missing_accessories"],
            ["counterfeit_claim"],
            ["serial_mismatch"],
            ["refund_pressure"],
        ] * 10
        results["intent_classifier"] = train_intent_classifier(
            sample_texts, sample_labels, model_type=payload.model_type,
            test_size=payload.test_size,
        )

    if payload.train_fraud:
        import numpy as np
        rng = np.random.default_rng(42)
        n_samples = 200
        embeddings = rng.normal(size=(n_samples, nlp_config.embedding_dim)).tolist()
        labels = [1 if i < 100 else 0 for i in range(n_samples)]
        results["fraud_classifier"] = train_fraud_classifier(
            embeddings, labels, model_type=payload.model_type,
            test_size=payload.test_size,
        )

    return {"trained": True, "results": results}


@router.post("/search")
async def search(
    payload: SearchRequest,
    predictor: NLPredictor = Depends(get_predictor),
):
    results = predictor.similarity.find_similar(
        payload.text, k=payload.k
    )
    if payload.min_score > 0:
        results = [r for r in results if r.get("score", 0) >= payload.min_score]
    return {
        "query": payload.text[:200],
        "results": results,
        "total": len(results),
    }


@router.get("/models")
async def models(
    predictor: NLPredictor = Depends(get_predictor),
):
    info = predictor.get_model_info()
    from .model_registry import NLPModelRegistry
    registry = NLPModelRegistry()
    versions = registry.list_versions()
    return {
        "active": info,
        "versions": versions,
        "total_versions": len(versions),
    }


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "embedding_dim": nlp_config.embedding_dim,
        "embedding_model": nlp_config.embedding_model,
        "supported_sources": nlp_config.supported_sources,
        "fraud_intents": nlp_config.fraud_intents,
    }
