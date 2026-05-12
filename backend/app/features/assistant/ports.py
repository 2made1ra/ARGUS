from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.features.assistant.dto import (
    BriefState,
    CatalogItemDetail,
    CatalogSearchFilters,
    ChatTurn,
    FoundCatalogItem,
    LLMStructuredRouterRequest,
    RenderedEventBrief,
    RouterDecision,
    SupplierVerificationResult,
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
        candidate_item_ids: list[UUID],
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
        filters: CatalogSearchFilters | None = None,
    ) -> list[FoundCatalogItem]: ...


class CatalogItemDetailsTool(Protocol):
    async def get_item_details(
        self,
        *,
        item_id: UUID,
    ) -> CatalogItemDetail | None: ...


class SupplierVerificationPort(Protocol):
    async def verify_by_inn_or_ogrn(
        self,
        *,
        inn: str | None,
        ogrn: str | None,
        supplier_name: str | None,
    ) -> SupplierVerificationResult: ...


class BriefRendererTool(Protocol):
    def render(
        self,
        *,
        brief: BriefState,
        selected_items: list[CatalogItemDetail],
        verification_results: list[SupplierVerificationResult],
        found_items: list[FoundCatalogItem] | None = None,
    ) -> RenderedEventBrief: ...


__all__ = [
    "AssistantRouter",
    "BriefRendererTool",
    "CatalogItemDetailsTool",
    "CatalogSearchTool",
    "LLMStructuredRouterPort",
    "SupplierVerificationPort",
]
