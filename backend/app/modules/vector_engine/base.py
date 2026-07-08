from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol


class VectorStore(ABC):
    @abstractmethod
    def add(self, embeddings: list[list[float]], metadata: list[dict[str, Any]]) -> None:
        ...

    @abstractmethod
    def search(self, query: list[float], k: int = 20) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        ...

    @abstractmethod
    def load(self, path: str) -> None:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...

    @abstractmethod
    def size(self) -> int:
        ...


class EmbeddingProvider(Protocol):
    dim: int
    def encode(self, texts: list[str]) -> list[list[float]]: ...
    def encode_single(self, text: str) -> list[float]: ...
