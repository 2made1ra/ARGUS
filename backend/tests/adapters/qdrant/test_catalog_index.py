from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from app.adapters.qdrant.catalog_index import QdrantCatalogIndex
from app.features.catalog.ports import CatalogVectorPoint
from qdrant_client.models import PointStruct


class FakeQdrantClient:
    def __init__(self) -> None:
        self.upsert_calls: list[dict[str, Any]] = []

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


@pytest.mark.asyncio
async def test_upsert_catalog_points_uses_price_item_id_vector_and_payload() -> None:
    client = FakeQdrantClient()
    index = QdrantCatalogIndex(client, "price_items_search_v1")  # type: ignore[arg-type]
    point_id = uuid4()
    point = CatalogVectorPoint(
        id=point_id,
        vector=[0.1, 0.2, 0.3],
        payload={
            "price_item_id": str(point_id),
            "category": "Аренда",
            "unit_price": 15000.0,
            "embedding_template_version": "prices_v1",
        },
    )

    await index.upsert_points([point])

    assert len(client.upsert_calls) == 1
    call = client.upsert_calls[0]
    assert call["collection_name"] == "price_items_search_v1"
    qdrant_point = call["points"][0]
    assert isinstance(qdrant_point, PointStruct)
    assert qdrant_point.id == point_id
    assert qdrant_point.vector == [0.1, 0.2, 0.3]
    assert qdrant_point.payload == point.payload


@pytest.mark.asyncio
async def test_upsert_catalog_points_returns_without_call_for_empty_points() -> None:
    client = FakeQdrantClient()
    index = QdrantCatalogIndex(client, "price_items_search_v1")  # type: ignore[arg-type]

    await index.upsert_points([])

    assert client.upsert_calls == []
