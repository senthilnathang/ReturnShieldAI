from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from .config import nlp_config
from .embeddings import NLPEmbeddingProvider

logger = logging.getLogger(__name__)


class SimilarityEngine:
    def __init__(self, provider: Optional[NLPEmbeddingProvider] = None):
        self.provider = provider or NLPEmbeddingProvider()
        self._store = None

    @property
    def store(self):
        if self._store is None:
            from .vector_store import NLPFaissStore
            self._store = NLPFaissStore(dim=self.provider.dim)
            p = Path(__file__).resolve().parents[3] / nlp_config.vector_store_path
            self._store.load(str(p))
        return self._store

    def find_similar(
        self,
        text: str,
        k: int = 20,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        if not text.strip():
            return []
        embedding = self.provider.encode_single(text)
        results = self.store.search(embedding, k=k)
        if min_score > 0:
            results = [r for r in results if r["score"] >= min_score]
        return results

    def index_cases(
        self,
        texts: list[str],
        metadata: list[dict[str, Any]],
    ):
        if not texts:
            return
        embeddings = self.provider.encode(texts)
        self.store.add(embeddings, metadata)
        from pathlib import Path
        p = Path(__file__).resolve().parents[3] / nlp_config.vector_store_path
        self.store.save(str(p))

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        import numpy as np
        emb_a = np.array(self.provider.encode_single(text_a))
        emb_b = np.array(self.provider.encode_single(text_b))
        dot = float(np.dot(emb_a, emb_b))
        norm = float(np.linalg.norm(emb_a) * np.linalg.norm(emb_b) + 1e-10)
        return round(dot / norm * 100.0, 2)

    def detect_template_usage(
        self,
        text: str,
        existing_texts: list[str],
        threshold: float = 0.85,
    ) -> list[dict[str, Any]]:
        matches = []
        for existing in existing_texts:
            score = self.compute_similarity(text, existing)
            if score >= threshold:
                matches.append({"text": existing[:200], "similarity": score})
        return matches
