from typing import Any
from uuid import uuid4

import pytest
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

from app.adapters.qdrant.index import QdrantVectorIndex
from app.core.domain.ids import DocumentId
from app.features.ingest.ports import VectorPoint


class FakeQdrantClient:
    def __init__(self) -> None:
        self.upsert_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    async def upsert(
        self,
        *,
        collection_name: str,
        points: list[PointStruct],
    ) -> None:
        self.upsert_calls.append(
            {
                "collection_name": collection_name,
                "points": points,
            },
        )

    async def delete(
        self,
        *,
        collection_name: str,
        points_selector: Filter,
    ) -> None:
        self.delete_calls.append(
            {
                "collection_name": collection_name,
                "points_selector": points_selector,
            },
        )


@pytest.mark.asyncio
async def test_upsert_chunks_returns_without_call_for_empty_points() -> None:
    client = FakeQdrantClient()
    index = QdrantVectorIndex(client, "document_chunks")  # type: ignore[arg-type]

    await index.upsert_chunks([])

    assert client.upsert_calls == []


@pytest.mark.asyncio
async def test_upsert_chunks_batches_points_by_256() -> None:
    client = FakeQdrantClient()
    index = QdrantVectorIndex(client, "document_chunks")  # type: ignore[arg-type]
    points = [
        VectorPoint(
            id=uuid4(),
            vector=[float(offset), 1.0],
            payload={"document_id": str(uuid4()), "chunk_index": offset},
        )
        for offset in range(257)
    ]

    await index.upsert_chunks(points)

    assert [len(call["points"]) for call in client.upsert_calls] == [256, 1]
    assert {call["collection_name"] for call in client.upsert_calls} == {
        "document_chunks",
    }
    first_qdrant_point = client.upsert_calls[0]["points"][0]
    assert isinstance(first_qdrant_point, PointStruct)
    assert first_qdrant_point.id == points[0].id
    assert first_qdrant_point.vector == points[0].vector
    assert first_qdrant_point.payload == points[0].payload


@pytest.mark.asyncio
async def test_delete_document_filters_by_document_id_payload() -> None:
    client = FakeQdrantClient()
    index = QdrantVectorIndex(client, "document_chunks")  # type: ignore[arg-type]
    document_id = DocumentId(uuid4())

    await index.delete_document(document_id)

    assert len(client.delete_calls) == 1
    call = client.delete_calls[0]
    assert call["collection_name"] == "document_chunks"
    selector = call["points_selector"]
    assert isinstance(selector, Filter)
    assert selector.must == [
        FieldCondition(
            key="document_id",
            match=MatchValue(value=str(document_id)),
        ),
    ]
