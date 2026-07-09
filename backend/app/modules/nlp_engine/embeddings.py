from __future__ import annotations

import logging
from typing import Optional

from .config import nlp_config

logger = logging.getLogger(__name__)


class NLPEmbeddingProvider:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or nlp_config.embedding_model
        self._model = None
        self._available = False
        self.dim = nlp_config.embedding_models.get(self.model_name, nlp_config.embedding_dim)
        try:
            import sentence_transformers
            self._available = True
        except ImportError:
            logger.warning("sentence-transformers not available; using TF-IDF fallback")

    def _lazy_load(self):
        if self._model is None and self._available:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._available:
            return self._fallback_encode(texts)
        self._lazy_load()
        if self._model is None:
            return self._fallback_encode(texts)
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def encode_single(self, text: str) -> list[float]:
        return self.encode([text])[0]

    def _fallback_encode(self, texts: list[str]) -> list[list[float]]:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
        v = TfidfVectorizer(max_features=self.dim, stop_words="english", sublinear_tf=True)
        matrix = v.fit_transform(texts)
        return matrix.toarray().tolist()
