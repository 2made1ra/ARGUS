from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.features.search.dto import SearchGroup, SearchHit


@runtime_checkable
class VectorSearch(Protocol):
    async def search(
        self,
        *,
        query_vector: list[float],
        limit: int,
        filter: dict[str, Any] | None = None,
        group_by: str | None = None,
        group_size: int = 3,
    ) -> list[SearchHit] | list[SearchGroup]: ...


__all__ = ["VectorSearch"]
