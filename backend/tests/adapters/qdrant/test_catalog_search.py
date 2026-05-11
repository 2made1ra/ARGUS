from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.adapters.qdrant.catalog_search import QdrantCatalogSearch
from app.features.catalog.ports import CatalogSearchFilters
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range


@dataclass
class FakeScoredPoint:
    id: UUID
    score: float
    payload: dict[str, Any] | None


@dataclass
class FakeQueryResponse:
    points: list[FakeScoredPoint]


class FakeQdrantClient:
    def __init__(self, point_id: UUID) -> None:
        self.query_points_calls: list[dict[str, Any]] = []
        self.response = FakeQueryResponse(
            points=[
                FakeScoredPoint(
                    id=point_id,
                    score=0.82,
                    payload={
                        "price_item_id": str(point_id),
                        "category": "Аренда",
                    },
                ),
            ],
        )

    async def query_points(self, **kwargs: Any) -> FakeQueryResponse:
        self.query_points_calls.append(kwargs)
        return self.response


@pytest.mark.asyncio
async def test_search_maps_qdrant_points_to_catalog_hits() -> None:
    price_item_id = uuid4()
    client = FakeQdrantClient(price_item_id)
    search = QdrantCatalogSearch(client, "price_items_search_v1")  # type: ignore[arg-type]

    hits = await search.search(
        query_vector=[0.1, 0.2, 0.3],
        filters=None,
        limit=5,
    )

    assert client.query_points_calls == [
        {
            "collection_name": "price_items_search_v1",
            "query": [0.1, 0.2, 0.3],
            "query_filter": None,
            "limit": 5,
            "with_payload": True,
        },
    ]
    assert len(hits) == 1
    assert hits[0].price_item_id == price_item_id
    assert hits[0].score == 0.82
    assert hits[0].payload == {
        "price_item_id": str(price_item_id),
        "category": "Аренда",
    }


@pytest.mark.asyncio
async def test_search_converts_catalog_filters_to_qdrant_filter() -> None:
    price_item_id = uuid4()
    client = FakeQdrantClient(price_item_id)
    search = QdrantCatalogSearch(client, "price_items_search_v1")  # type: ignore[arg-type]

    await search.search(
        query_vector=[0.1, 0.2, 0.3],
        filters=CatalogSearchFilters(
            category="Аренда",
            supplier_city="г. Москва",
            unit_price_min=1000.0,
            unit_price_max=5000.0,
            embedding_template_version="prices_v1",
        ),
        limit=10,
    )

    assert client.query_points_calls[0]["query_filter"] == Filter(
        must=[
            FieldCondition(
                key="category",
                match=MatchValue(value="Аренда"),
            ),
            FieldCondition(
                key="supplier_city",
                match=MatchValue(value="г. Москва"),
            ),
            FieldCondition(
                key="embedding_template_version",
                match=MatchValue(value="prices_v1"),
            ),
            FieldCondition(
                key="unit_price",
                range=Range(gte=1000.0, lte=5000.0),
            ),
        ],
    )
