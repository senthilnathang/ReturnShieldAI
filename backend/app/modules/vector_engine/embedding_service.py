from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from backend.app.modules.vector_engine.base import EmbeddingProvider
from backend.app.modules.vector_engine.providers.faiss_provider import FaissVectorStore

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "embeddings.yaml"


def _load_config() -> dict[str, Any]:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {"active_model": "all-MiniLM-L6-v2", "models": {}, "vector_store": {"provider": "faiss", "index_path": "models/vector_store/faiss.index"}}


class SentenceTransformerProvider:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._available = False
        self.dim = self._resolve_dim()
        try:
            import sentence_transformers
            self._available = True
        except ImportError:
            logger.warning("sentence-transformers not installed. Embedding service will use TF-IDF fallback.")

    def _resolve_dim(self) -> int:
        dim_map = {
            "all-MiniLM-L6-v2": 384,
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-large-en-v1.5": 1024,
            "intfloat/e5-large-v2": 1024,
            "nvidia/NV-Embed-v2": 4096,
        }
        return dim_map.get(self.model_name, 384)

    def _lazy_load(self):
        if self._model is None and self._available:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            if hasattr(self._model, "get_sentence_embedding_dimension"):
                self.dim = self._model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._available:
            return self._fallback_encode(texts)
        self._lazy_load()
        if self._model is None:
            return self._fallback_encode(texts)
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    def encode_single(self, text: str) -> list[float]:
        return self.encode([text])[0]

    def _fallback_encode(self, texts: list[str]) -> list[list[float]]:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
        v = TfidfVectorizer(max_features=self.dim, stop_words="english", sublinear_tf=True)
        matrix = v.fit_transform(texts)
        return matrix.toarray().tolist()


class EmbeddingService:
    def __init__(self):
        config = _load_config()
        model_name = config.get("active_model", "all-MiniLM-L6-v2")
        self.provider = SentenceTransformerProvider(model_name)
        vs_config = config.get("vector_store", {})
        store_path = vs_config.get("index_path", "models/vector_store/faiss.index")
        self._resolved_path = str(Path(__file__).resolve().parents[4] / store_path)
        self.store = FaissVectorStore(dim=self.provider.dim)
        self.store.load(self._resolved_path)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.provider.encode(texts)

    def embed_text(self, text: str) -> list[float]:
        return self.provider.encode_single(text)

    def add_cases(self, texts: list[str], metadata: list[dict[str, Any]]) -> None:
        embeddings = self.embed_texts(texts)
        self.store.add(embeddings, metadata)
        self.store.save(self._resolved_path)

    def search_similar(self, text: str, k: int = 20) -> list[dict[str, Any]]:
        query = self.embed_text(text)
        return self.store.search(query, k=k)

    def clear(self) -> None:
        self.store.clear()
        self.store.save(self._resolved_path)

    def size(self) -> int:
        return self.store.size()
