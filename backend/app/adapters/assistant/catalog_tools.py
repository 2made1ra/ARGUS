from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.features.assistant.dto import (
    CatalogItemDetail,
    CatalogSearchFilters,
    FoundCatalogItem,
)
from app.features.assistant.dto import MatchReason as AssistantMatchReason
from app.features.catalog.dto import FoundPriceItem, SearchPriceItemsFilters
from app.features.catalog.ports import PriceItemNotFound
from app.features.catalog.use_cases.get_price_item import GetPriceItemUseCase
from app.features.catalog.use_cases.search_price_items import SearchPriceItemsUseCase


class CatalogSearchToolAdapter:
    def __init__(self, search: SearchPriceItemsUseCase) -> None:
        self._search = search

    async def search_items(
        self,
        *,
        query: str,
        limit: int,
        filters: CatalogSearchFilters | None = None,
    ) -> list[FoundCatalogItem]:
        result = await self._search.search_items(
            query=query,
            filters=_catalog_search_filters(filters),
            limit=limit,
        )
        return [_found_catalog_item(item) for item in result.items]


class CatalogItemDetailsToolAdapter:
    def __init__(self, details: GetPriceItemUseCase) -> None:
        self._details = details

    async def get_item_details(
        self,
        *,
        item_id: UUID,
    ) -> CatalogItemDetail | None:
        try:
            item, _sources = await self._details.execute(item_id)
        except PriceItemNotFound:
            return None
        return CatalogItemDetail(
            id=item.id,
            name=item.name,
            category=item.category,
            unit=item.unit,
            unit_price=item.unit_price,
            supplier=item.supplier,
            supplier_inn=item.supplier_inn,
            supplier_city=item.supplier_city,
            supplier_phone=item.supplier_phone,
            supplier_email=item.supplier_email,
            supplier_status=item.supplier_status,
            source_text=item.source_text,
        )


def _found_catalog_item(item: FoundPriceItem) -> FoundCatalogItem:
    return FoundCatalogItem(
        id=item.id,
        score=item.score,
        name=item.name,
        category=item.category,
        unit=item.unit,
        unit_price=item.unit_price,
        supplier=item.supplier,
        supplier_city=item.supplier_city,
        source_text_snippet=item.source_text_snippet,
        source_text_full_available=item.source_text_full_available,
        match_reason=AssistantMatchReason(
            code=item.match_reason.code,
            label=item.match_reason.label,
        ),
        matched_service_category=item.service_category,
        matched_service_categories=(
            [item.service_category] if item.service_category is not None else []
        ),
    )


def _catalog_search_filters(
    filters: CatalogSearchFilters | None,
) -> SearchPriceItemsFilters:
    if filters is None:
        return SearchPriceItemsFilters()
    return SearchPriceItemsFilters(
        supplier_city_normalized=filters.supplier_city_normalized,
        category=filters.category,
        service_category=filters.service_category,
        supplier_status_normalized=filters.supplier_status_normalized,
        has_vat=filters.has_vat,
        vat_mode=filters.vat_mode,
        unit_price_min=_decimal_or_none(filters.unit_price_min),
        unit_price_max=_decimal_or_none(filters.unit_price_max),
    )


def _decimal_or_none(value: int | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


__all__ = [
    "CatalogItemDetailsToolAdapter",
    "CatalogSearchToolAdapter",
]
