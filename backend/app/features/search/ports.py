from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.features.search.dto import ChatMessage, RagContextChunk, SearchGroup, SearchHit


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


@runtime_checkable
class ChatLLM(Protocol):
    async def complete(self, messages: list[ChatMessage]) -> str: ...


@runtime_checkable
class Reranker(Protocol):
    async def rerank(
        self,
        *,
        query: str,
        chunks: list[RagContextChunk],
        top_k: int,
    ) -> list[RagContextChunk]: ...


__all__ = ["ChatLLM", "Reranker", "VectorSearch"]
