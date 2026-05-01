from __future__ import annotations

from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter

from app.features.search.dto import SearchGroup, SearchHit


class QdrantVectorSearch:
    def __init__(self, client: AsyncQdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    async def search(
        self,
        *,
        query_vector: list[float],
        limit: int,
        filter: dict[str, Any] | None = None,
        group_by: str | None = None,
        group_size: int = 3,
    ) -> list[SearchHit] | list[SearchGroup]:
        query_filter = _filter_from_dict(filter)
        if group_by is not None:
            result = await self._client.query_points_groups(
                collection_name=self._collection,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                group_by=group_by,
                group_size=group_size,
                with_payload=True,
            )
            return [_group_from_qdrant(group) for group in result.groups]

        response = await self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return [_hit_from_qdrant(hit) for hit in response.points]


def _filter_from_dict(value: dict[str, Any] | None) -> Filter | None:
    if value is None:
        return None
    return Filter.model_validate(value)


def _group_from_qdrant(group: Any) -> SearchGroup:
    return SearchGroup(
        group_key=str(group.id),
        hits=[_hit_from_qdrant(hit) for hit in group.hits],
    )


def _hit_from_qdrant(hit: Any) -> SearchHit:
    return SearchHit(
        id=_uuid_from_qdrant_id(hit.id),
        score=float(hit.score),
        payload=dict(hit.payload or {}),
    )


def _uuid_from_qdrant_id(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


__all__ = ["QdrantVectorSearch"]
