from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class NLPConfig:
    artifact_root: Path = Path(__file__).resolve().parents[3] / "models" / "nlp"
    vector_store_path: str = "models/vector_store/nlp_faiss.index"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "nlp_fraud_cases"
    vector_store_provider: str = "faiss"
    spacy_model: str = "en_core_web_sm"
    max_text_length: int = 10000
    stopwords_language: str = "english"
    enable_spelling_correction: bool = False
    enable_lemmatization: bool = True
    similarity_top_k: int = 20
    intent_threshold: float = 0.3
    fraud_threshold: float = 0.5
    high_risk_threshold: float = 0.75
    manual_review_threshold: float = 0.40
    cache_ttl_seconds: int = 600
    prediction_stream: str = "nlp:prediction:stream"
    train_stream: str = "nlp:train:stream"
    supported_sources: list[str] = field(default_factory=lambda: [
        "return_reason", "customer_chat", "customer_email",
        "warehouse_notes", "analyst_notes", "courier_remarks",
    ])
    fraud_intents: list[str] = field(default_factory=lambda: [
        "empty_box_claim", "fake_damaged_item", "item_not_received",
        "refund_urgency", "chargeback_threat", "return_abuse",
        "missing_accessories", "counterfeit_claim", "serial_mismatch",
        "refund_pressure",
    ])
    embedding_models: dict[str, int] = field(default_factory=lambda: {
        "all-MiniLM-L6-v2": 384,
        "BAAI/bge-small-en-v1.5": 384,
        "BAAI/bge-base-en-v1.5": 768,
        "BAAI/bge-large-en-v1.5": 1024,
        "intfloat/multilingual-e5-base": 768,
    })
    fraud_keywords: dict[str, list[str]] = field(default_factory=lambda: {
        "empty_box_claim": ["empty box", "nothing inside", "box was empty", "received empty", "package had nothing"],
        "fake_damaged_item": ["arrived damaged", "broken when opened", "cracked screen", "not working", "defective item"],
        "item_not_received": ["never arrived", "didn't receive", "lost in transit", "not delivered", "missing package"],
        "refund_urgency": ["refund immediately", "need refund now", "urgent refund", "refund today", "asap refund"],
        "chargeback_threat": ["chargeback", "dispute with bank", "call my bank", "credit card dispute", "reverse charge"],
        "return_abuse": ["used it now returning", "worn once", "bought for event", "no longer need", "changed mind"],
        "missing_accessories": ["missing parts", "accessories not included", "incomplete item", "missing charger", "no cables"],
        "counterfeit_claim": ["fake product", "not authentic", "counterfeit", "replica", "knockoff"],
        "serial_mismatch": ["serial number different", "imei mismatch", "wrong serial", "serial doesn't match", "different imei"],
        "refund_pressure": ["escalate", "manager now", "complaint", "legal action", "lawyer", "sue", "attorney"],
    })


nlp_config = NLPConfig()
