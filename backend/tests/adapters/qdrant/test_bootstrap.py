from types import SimpleNamespace
from typing import Any

import pytest
from app.adapters.qdrant.bootstrap import (
    QdrantSchemaMismatch,
    bootstrap_catalog_collection,
    bootstrap_collection,
    bootstrap_qdrant_collections,
)
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseVectorParams,
    VectorParams,
)


class FakeQdrantClient:
    def __init__(
        self,
        *,
        exists: bool | dict[str, bool],
        vectors: object | dict[str, object | None] | None = None,
    ) -> None:
        self.exists = exists
        self.vectors = vectors
        self.info = _collection_info(vectors=vectors)
        self.create_calls: list[dict[str, Any]] = []
        self.get_calls: list[str] = []
        self.payload_index_calls: list[dict[str, Any]] = []

    async def collection_exists(self, collection_name: str) -> bool:
        if isinstance(self.exists, dict):
            return self.exists[collection_name]
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
        if isinstance(self.exists, dict) and isinstance(self.vectors, dict):
            return _collection_info(vectors=self.vectors[collection_name])
        return self.info

    async def create_payload_index(
        self,
        *,
        collection_name: str,
        field_name: str,
        field_schema: PayloadSchemaType,
    ) -> None:
        self.payload_index_calls.append(
            {
                "collection_name": collection_name,
                "field_name": field_name,
                "field_schema": field_schema,
            },
        )


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


@pytest.mark.asyncio
async def test_bootstrap_catalog_collection_creates_payload_indexes() -> None:
    client = FakeQdrantClient(exists=False)

    await bootstrap_catalog_collection(
        client,  # type: ignore[arg-type]
        "price_items_search_v1",
        768,
    )

    assert client.create_calls == [
        {
            "collection_name": "price_items_search_v1",
            "vectors_config": VectorParams(size=768, distance=Distance.COSINE),
        },
    ]
    assert client.payload_index_calls == [
        {
            "collection_name": "price_items_search_v1",
            "field_name": "price_item_id",
            "field_schema": PayloadSchemaType.UUID,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "import_batch_id",
            "field_schema": PayloadSchemaType.UUID,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "source_file_id",
            "field_schema": PayloadSchemaType.UUID,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "category",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "category_normalized",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "section",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "section_normalized",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "unit",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "unit_price",
            "field_schema": PayloadSchemaType.FLOAT,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "has_vat",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "vat_mode",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "supplier_city",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "supplier_city_normalized",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "supplier_status",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "supplier_status_normalized",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
        {
            "collection_name": "price_items_search_v1",
            "field_name": "embedding_template_version",
            "field_schema": PayloadSchemaType.KEYWORD,
        },
    ]


@pytest.mark.asyncio
async def test_bootstrap_qdrant_collections_keeps_document_collection_separate(
) -> None:
    client = FakeQdrantClient(
        exists={"document_chunks": False, "price_items_search_v1": False},
        vectors={"document_chunks": None, "price_items_search_v1": None},
    )

    await bootstrap_qdrant_collections(
        client,  # type: ignore[arg-type]
        document_collection="document_chunks",
        document_dim=384,
        catalog_collection="price_items_search_v1",
        catalog_dim=768,
    )

    assert client.create_calls == [
        {
            "collection_name": "document_chunks",
            "vectors_config": VectorParams(size=384, distance=Distance.COSINE),
        },
        {
            "collection_name": "price_items_search_v1",
            "vectors_config": VectorParams(size=768, distance=Distance.COSINE),
        },
    ]
    assert {call["collection_name"] for call in client.payload_index_calls} == {
        "price_items_search_v1",
    }
