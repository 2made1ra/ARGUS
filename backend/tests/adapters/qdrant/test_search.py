from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.adapters.qdrant.search import QdrantVectorSearch
from app.features.search.dto import SearchGroup, SearchHit


@dataclass
class FakeScoredPoint:
    id: UUID
    score: float
    payload: dict[str, Any] | None


@dataclass
class FakeQueryResponse:
    points: list[FakeScoredPoint]


@dataclass
class FakePointGroup:
    id: str
    hits: list[FakeScoredPoint]


@dataclass
class FakeGroupsResult:
    groups: list[FakePointGroup]


class FakeQdrantClient:
    def __init__(self) -> None:
        self.query_points_calls: list[dict[str, Any]] = []
        self.query_points_groups_calls: list[dict[str, Any]] = []
        self.points_response = FakeQueryResponse(
            points=[
                FakeScoredPoint(
                    id=uuid4(),
                    score=0.71,
                    payload={"text": "first"},
                ),
            ],
        )
        self.groups_response = FakeGroupsResult(
            groups=[
                FakePointGroup(
                    id=str(uuid4()),
                    hits=[
                        FakeScoredPoint(
                            id=uuid4(),
                            score=0.95,
                            payload={"text": "group hit"},
                        ),
                    ],
                ),
            ],
        )

    async def query_points(self, **kwargs: Any) -> FakeQueryResponse:
        self.query_points_calls.append(kwargs)
        return self.points_response

    async def query_points_groups(self, **kwargs: Any) -> FakeGroupsResult:
        self.query_points_groups_calls.append(kwargs)
        return self.groups_response


@pytest.mark.asyncio
async def test_search_uses_query_points_for_plain_hits() -> None:
    client = FakeQdrantClient()
    search = QdrantVectorSearch(client, "document_chunks")  # type: ignore[arg-type]
    query_filter = {
        "must": [
            {
                "key": "document_id",
                "match": {"value": str(uuid4())},
            },
        ],
    }

    hits = await search.search(
        query_vector=[0.1, 0.2],
        limit=10,
        filter=query_filter,
    )

    assert client.query_points_groups_calls == []
    assert len(client.query_points_calls) == 1
    call = client.query_points_calls[0]
    assert call["collection_name"] == "document_chunks"
    assert call["query"] == [0.1, 0.2]
    assert call["limit"] == 10
    assert call["with_payload"] is True
    must = cast(list[dict[str, Any]], query_filter["must"])
    match = cast(dict[str, str], must[0]["match"])
    assert call["query_filter"] == Filter(
        must=[
            FieldCondition(
                key="document_id",
                match=MatchValue(value=match["value"]),
            ),
        ],
    )
    plain_hits = cast(list[SearchHit], hits)
    assert plain_hits[0].id == client.points_response.points[0].id
    assert plain_hits[0].score == 0.71
    assert plain_hits[0].payload == {"text": "first"}


@pytest.mark.asyncio
async def test_search_uses_query_points_groups_for_grouped_hits() -> None:
    client = FakeQdrantClient()
    search = QdrantVectorSearch(client, "document_chunks")  # type: ignore[arg-type]

    groups = await search.search(
        query_vector=[0.3, 0.4],
        limit=200,
        group_by="contractor_entity_id",
        group_size=3,
    )

    assert client.query_points_calls == []
    assert client.query_points_groups_calls == [
        {
            "collection_name": "document_chunks",
            "query": [0.3, 0.4],
            "query_filter": None,
            "limit": 200,
            "group_by": "contractor_entity_id",
            "group_size": 3,
            "with_payload": True,
        },
    ]
    grouped_hits = cast(list[SearchGroup], groups)
    assert len(grouped_hits) == 1
    assert grouped_hits[0].group_key == client.groups_response.groups[0].id
    assert grouped_hits[0].hits[0].score == 0.95
    assert grouped_hits[0].hits[0].payload == {"text": "group hit"}
