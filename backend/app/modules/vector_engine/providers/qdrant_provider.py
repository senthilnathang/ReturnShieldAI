from __future__ import annotations

from typing import Any

from backend.app.modules.vector_engine.base import VectorStore


class QdrantVectorStore(VectorStore):
    def __init__(self, collection: str = "fraud_cases", url: str = "http://localhost:6333"):
        self.collection = collection
        self.url = url
        self._storage: list[tuple[list[float], dict[str, Any]]] = []

    def add(self, embeddings: list[list[float]], metadata: list[dict[str, Any]]) -> None:
        for emb, meta in zip(embeddings, metadata):
            self._storage.append((emb, meta))

    def search(self, query: list[float], k: int = 20) -> list[dict[str, Any]]:
        import numpy as np
        if not self._storage:
            return []
        q = np.array(query, dtype=np.float32)
        scored = []
        for emb, meta in self._storage:
            e = np.array(emb, dtype=np.float32)
            sim = float(np.dot(q, e) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-10))
            scored.append({"score": round(max(0.0, sim * 100.0), 2), "metadata": meta})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def save(self, path: str) -> None:
        import joblib
        import json
        data = [(e.tolist() if hasattr(e, 'tolist') else e, m) for e, m in self._storage]
        joblib.dump(data, path)

    def load(self, path: str) -> None:
        import joblib
        import os
        if os.path.exists(path):
            self._storage = joblib.load(path)

    def clear(self) -> None:
        self._storage.clear()

    def size(self) -> int:
        return len(self._storage)
