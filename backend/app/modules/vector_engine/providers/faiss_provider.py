from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import faiss

from backend.app.modules.vector_engine.base import VectorStore


class FaissVectorStore(VectorStore):
    def __init__(self, dim: int = 384, similarity: str = "cosine"):
        self.dim = dim
        self.similarity = similarity
        self._reset_index()
        self.metadata: list[dict[str, Any]] = []

    def _reset_index(self) -> None:
        if self.similarity == "cosine":
            self.index = faiss.IndexFlatIP(self.dim)
        else:
            self.index = faiss.IndexFlatL2(self.dim)

    def add(self, embeddings: list[list[float]], metadata: list[dict[str, Any]]) -> None:
        if not embeddings:
            return
        if len(embeddings[0]) != self.dim:
            self.dim = len(embeddings[0])
            self._reset_index()
            self.metadata = []
        vectors = np.array(embeddings, dtype=np.float32)
        if self.similarity == "cosine":
            faiss.normalize_L2(vectors)
        self.index.add(vectors)
        self.metadata.extend(metadata)

    def search(self, query: list[float], k: int = 20) -> list[dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
        q = np.array([query], dtype=np.float32)
        if self.similarity == "cosine":
            faiss.normalize_L2(q)
        distances, indices = self.index.search(q, min(k, self.index.ntotal))
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            score = float(dist) if self.similarity == "cosine" else max(0.0, 100.0 - float(dist))
            results.append({
                "score": round(min(100.0, max(0.0, score * 100.0)), 2),
                "metadata": self.metadata[idx],
            })
        return sorted(results, key=lambda x: x["score"], reverse=True)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, path)
        import joblib
        meta_path = path.replace(".index", "_meta.joblib")
        joblib.dump(self.metadata, meta_path)

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            return
        try:
            loaded = faiss.read_index(path)
            if loaded.d == self.dim:
                self.index = loaded
        except Exception:
            pass
        meta_path = path.replace(".index", "_meta.joblib")
        if os.path.exists(meta_path):
            import joblib
            try:
                self.metadata = joblib.load(meta_path)
            except Exception:
                self.metadata = []

    def clear(self) -> None:
        self.index.reset()
        self.metadata.clear()

    def size(self) -> int:
        return self.index.ntotal
