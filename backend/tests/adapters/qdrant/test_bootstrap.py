from types import SimpleNamespace
from typing import Any

import pytest
from qdrant_client.models import Distance, SparseVectorParams, VectorParams

from app.adapters.qdrant.bootstrap import QdrantSchemaMismatch, bootstrap_collection


class FakeQdrantClient:
    def __init__(self, *, exists: bool, vectors: object | None = None) -> None:
        self.exists = exists
        self.info = _collection_info(vectors=vectors)
        self.create_calls: list[dict[str, Any]] = []
        self.get_calls: list[str] = []

    async def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    async def create_collection(
        self,
        collection_name: str,
        vectors_config: VectorParams,
    ) -> None:
        self.create_calls.append(
            {
                "collection_name": collection_name,
                "vectors_config": vectors_config,
            },
        )

    async def get_collection(self, collection_name: str) -> SimpleNamespace:
        self.get_calls.append(collection_name)
        return self.info


def _collection_info(
    *,
    vectors: object | None,
    sparse_vectors: dict[str, SparseVectorParams] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=vectors,
                sparse_vectors=sparse_vectors,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_bootstrap_collection_creates_absent_collection() -> None:
    client = FakeQdrantClient(exists=False)

    await bootstrap_collection(client, "document_chunks", 768)  # type: ignore[arg-type]

    assert client.get_calls == []
    assert len(client.create_calls) == 1
    call = client.create_calls[0]
    assert call["collection_name"] == "document_chunks"
    assert call["vectors_config"] == VectorParams(size=768, distance=Distance.COSINE)


@pytest.mark.asyncio
async def test_bootstrap_collection_returns_for_matching_collection() -> None:
    client = FakeQdrantClient(
        exists=True,
        vectors=VectorParams(size=768, distance=Distance.COSINE),
    )

    await bootstrap_collection(client, "document_chunks", 768)  # type: ignore[arg-type]

    assert client.get_calls == ["document_chunks"]
    assert client.create_calls == []


@pytest.mark.asyncio
async def test_bootstrap_collection_raises_for_different_vector_size() -> None:
    client = FakeQdrantClient(
        exists=True,
        vectors=VectorParams(size=384, distance=Distance.COSINE),
    )

    with pytest.raises(QdrantSchemaMismatch) as exc_info:
        await bootstrap_collection(client, "document_chunks", 768)  # type: ignore[arg-type]

    assert exc_info.value.collection == "document_chunks"
    assert exc_info.value.expected_dim == 768
    assert exc_info.value.actual_dim == 384
    assert client.create_calls == []


@pytest.mark.asyncio
async def test_bootstrap_collection_raises_for_named_vectors() -> None:
    client = FakeQdrantClient(
        exists=True,
        vectors={"dense": VectorParams(size=768, distance=Distance.COSINE)},
    )

    with pytest.raises(QdrantSchemaMismatch):
        await bootstrap_collection(client, "document_chunks", 768)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_bootstrap_collection_raises_for_sparse_vectors() -> None:
    client = FakeQdrantClient(
        exists=True,
        vectors=VectorParams(size=768, distance=Distance.COSINE),
    )
    client.info = _collection_info(
        vectors=VectorParams(size=768, distance=Distance.COSINE),
        sparse_vectors={"sparse": SparseVectorParams()},
    )

    with pytest.raises(QdrantSchemaMismatch):
        await bootstrap_collection(client, "document_chunks", 768)  # type: ignore[arg-type]
