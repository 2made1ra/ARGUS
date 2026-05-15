from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.features.assistant.dto import (
    BriefState,
    CatalogItemDetail,
    CatalogSearchFilters,
    FoundCatalogItem,
    RenderedEventBrief,
    SupplierVerificationResult,
)


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


class SupplierVerificationTool(Protocol):
    async def verify_by_inn_or_ogrn(
        self,
        *,
        inn: str | None,
        ogrn: str | None,
        supplier_name: str | None,
    ) -> SupplierVerificationResult: ...


class EventBriefRenderTool(Protocol):
    def render(
        self,
        *,
        brief: BriefState,
        selected_items: list[CatalogItemDetail],
        verification_results: list[SupplierVerificationResult],
        found_items: list[FoundCatalogItem] | None = None,
    ) -> RenderedEventBrief: ...


__all__ = [
    "CatalogItemDetailsTool",
    "CatalogSearchTool",
    "EventBriefRenderTool",
    "SupplierVerificationTool",
]
