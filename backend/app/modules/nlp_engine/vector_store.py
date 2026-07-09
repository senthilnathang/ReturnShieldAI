from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .config import nlp_config

logger = logging.getLogger(__name__)


class NLPFaissStore:
    def __init__(self, dim: int = 384):
        self.dim = dim
        self._index = None
        self.metadata: list[dict[str, Any]] = []
        self._faiss = None
        try:
            import faiss
            self._faiss = faiss
            self._reset_index()
        except ImportError:
            logger.warning("faiss not available; using in-memory brute-force")

    def _reset_index(self):
        if self._faiss is not None:
            self._index = self._faiss.IndexFlatIP(self.dim)

    def add(self, embeddings: list[list[float]], metadata: list[dict[str, Any]]):
        if not embeddings:
            return
        if self._faiss is not None:
            vectors = np.array(embeddings, dtype=np.float32)
            self._faiss.normalize_L2(vectors)
            if self._index is None or self._index.d != len(embeddings[0]):
                self.dim = len(embeddings[0])
                self._reset_index()
                self.metadata = []
            self._index.add(vectors)
        self.metadata.extend(metadata)

    def search(self, query: list[float], k: int = 20) -> list[dict[str, Any]]:
        if self._faiss is not None and self._index is not None and self._index.ntotal > 0:
            q = np.array([query], dtype=np.float32)
            self._faiss.normalize_L2(q)
            distances, indices = self._index.search(q, min(k, self._index.ntotal))
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0 or idx >= len(self.metadata):
                    continue
                score = float(dist)
                results.append({
                    "score": round(min(100.0, max(0.0, score * 100.0)), 2),
                    "metadata": self.metadata[idx],
                })
            return sorted(results, key=lambda x: x["score"], reverse=True)
        return self._bruteforce_search(query, k)

    def _bruteforce_search(self, query: list[float], k: int) -> list[dict[str, Any]]:
        if not self.metadata:
            return []
        q = np.array(query, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        scored = []
        for i, meta in enumerate(self.metadata):
            scored.append((meta, 0.0))
        return sorted(scored, key=lambda x: x[1], reverse=True)[:k]

    def save(self, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if self._faiss is not None and self._index is not None:
            self._faiss.write_index(self._index, str(p))
        import joblib
        meta_path = p.with_suffix(".meta.joblib")
        joblib.dump(self.metadata, meta_path)

    def load(self, path: str):
        p = Path(path)
        if not p.exists():
            return
        if self._faiss is not None:
            try:
                loaded = self._faiss.read_index(str(p))
                if loaded.d == self.dim:
                    self._index = loaded
            except Exception:
                pass
        meta_path = p.with_suffix(".meta.joblib")
        if meta_path.exists():
            import joblib
            try:
                self.metadata = joblib.load(meta_path)
            except Exception:
                self.metadata = []

    def clear(self):
        if self._faiss is not None:
            self._reset_index()
        self.metadata.clear()

    def size(self) -> int:
        if self._faiss is not None and self._index is not None:
            return self._index.ntotal
        return len(self.metadata)
