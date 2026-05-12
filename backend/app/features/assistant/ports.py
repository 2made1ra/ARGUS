from __future__ import annotations

from typing import Protocol

from app.features.assistant.dto import (
    BriefState,
    ChatTurn,
    FoundCatalogItem,
    LLMStructuredRouterRequest,
    RouterDecision,
    VisibleCandidate,
)


class AssistantRouter(Protocol):
    async def route(
        self,
        *,
        message: str,
        brief: BriefState,
        recent_turns: list[ChatTurn],
        visible_candidates: list[VisibleCandidate],
    ) -> RouterDecision: ...


class LLMStructuredRouterPort(Protocol):
    async def route_structured(
        self,
        *,
        prompt: LLMStructuredRouterRequest,
    ) -> str: ...


class CatalogSearchTool(Protocol):
    async def search_items(
        self,
        *,
        query: str,
        limit: int,
    ) -> list[FoundCatalogItem]: ...


__all__ = ["AssistantRouter", "CatalogSearchTool", "LLMStructuredRouterPort"]
