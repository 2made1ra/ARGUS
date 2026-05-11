from __future__ import annotations

from typing import Protocol

from app.features.assistant.dto import BriefState, FoundCatalogItem, RouterDecision


class AssistantRouter(Protocol):
    async def route(self, *, message: str, brief: BriefState) -> RouterDecision: ...


class CatalogSearchTool(Protocol):
    async def search_items(
        self,
        *,
        query: str,
        limit: int,
    ) -> list[FoundCatalogItem]: ...


__all__ = ["AssistantRouter", "CatalogSearchTool"]
