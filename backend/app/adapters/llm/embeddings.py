from collections.abc import Iterator
from typing import Any

import httpx


class EmbeddingDimensionMismatch(Exception):
    def __init__(self, actual: int, expected: int) -> None:
        super().__init__(
            f"Embedding dimension mismatch: expected {expected}, got {actual}",
        )
        self.actual = actual
        self.expected = expected


class LMStudioEmbeddings:
    def __init__(
        self,
        *,
        base_url: str,
        model: str = "nomic-embed-text-v1.5",
        batch_size: int = 32,
        timeout: float = 60.0,
        embedding_dim: int = 768,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be greater than 0")

        self._base_url = base_url.rstrip("/")
        self._model = model
        self._batch_size = batch_size
        self._timeout = timeout
        self._embedding_dim = embedding_dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for batch in _batches(texts, self._batch_size):
                response = await client.post(
                    self._embeddings_url(),
                    json={"model": self._model, "input": batch},
                )
                response.raise_for_status()
                batch_embeddings = self._parse_embeddings(response.json())
                if len(batch_embeddings) != len(batch):
                    raise ValueError(
                        "Embedding response count does not match request count",
                    )
                embeddings.extend(batch_embeddings)

        return embeddings

    def _parse_embeddings(self, payload: dict[str, Any]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for item in payload["data"]:
            embedding = item["embedding"]
            if len(embedding) != self._embedding_dim:
                raise EmbeddingDimensionMismatch(len(embedding), self._embedding_dim)
            embeddings.append(embedding)
        return embeddings

    def _embeddings_url(self) -> str:
        return f"{self._base_url}/embeddings"


def _batches(texts: list[str], batch_size: int) -> Iterator[list[str]]:
    for start in range(0, len(texts), batch_size):
        yield texts[start : start + batch_size]


__all__ = ["EmbeddingDimensionMismatch", "LMStudioEmbeddings"]
