from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.assistant.catalog_tools import (
    CatalogItemDetailsToolAdapter,
    CatalogSearchToolAdapter,
)
from app.features.assistant.dto import CatalogSearchFilters, MatchReason
from app.features.catalog.dto import (
    FoundPriceItem,
    SearchPriceItemsFilters,
    SearchPriceItemsResult,
)
from app.features.catalog.dto import (
    MatchReason as CatalogMatchReason,
)
from app.features.catalog.ports import PriceItemNotFound


class FakeSearchUseCase:
    def __init__(self, result: SearchPriceItemsResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def search_items(
        self,
        *,
        query: str,
        filters: object,
        limit: int,
    ) -> SearchPriceItemsResult:
        self.calls.append({"query": query, "filters": filters, "limit": limit})
        return self.result


class FakeDetailsUseCase:
    def __init__(self, item: object | None) -> None:
        self.item = item
        self.calls: list[object] = []

    async def execute(self, item_id: object) -> tuple[object, list[object]]:
        self.calls.append(item_id)
        if self.item is None:
            raise PriceItemNotFound(item_id)
        return self.item, []


@pytest.mark.asyncio
async def test_catalog_search_tool_adapter_maps_filters_and_results() -> None:
    item_id = uuid4()
    found = FoundPriceItem(
        id=item_id,
        score=0.8,
        name="Световой комплект",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО Свет",
        supplier_city="Екатеринбург",
        source_text_snippet="Свет для сцены",
        source_text_full_available=True,
        match_reason=CatalogMatchReason(code="semantic", label="Семантика"),
        service_category="свет",
    )
    search = FakeSearchUseCase(SearchPriceItemsResult(items=[found]))
    adapter = CatalogSearchToolAdapter(search)  # type: ignore[arg-type]
    filters = CatalogSearchFilters(
        supplier_city_normalized="екатеринбург",
        service_category="свет",
        unit_price_min=1000,
        unit_price_max=20000,
    )

    result = await adapter.search_items(query="свет", limit=5, filters=filters)

    assert len(result) == 1
    assert result[0].id == item_id
    assert result[0].match_reason == MatchReason(
        code="semantic",
        label="Семантика",
    )
    assert result[0].matched_service_category == "свет"
    assert result[0].matched_service_categories == ["свет"]
    call_filters = search.calls[0]["filters"]
    assert isinstance(call_filters, SearchPriceItemsFilters)
    assert call_filters.supplier_city_normalized == "екатеринбург"
    assert call_filters.service_category == "свет"
    assert call_filters.unit_price_min == Decimal("1000")
    assert call_filters.unit_price_max == Decimal("20000")


@pytest.mark.asyncio
async def test_catalog_item_details_tool_adapter_maps_catalog_item() -> None:
    item_id = uuid4()
    item = SimpleNamespace(
        id=item_id,
        name="Световой комплект",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО Свет",
        supplier_inn="6671000000",
        supplier_city="Екатеринбург",
        supplier_phone=None,
        supplier_email=None,
        supplier_status="active",
        source_text="Свет для сцены",
    )
    details = FakeDetailsUseCase(item)
    adapter = CatalogItemDetailsToolAdapter(details)  # type: ignore[arg-type]

    result = await adapter.get_item_details(item_id=item_id)

    assert result is not None
    assert result.id == item_id
    assert result.supplier_inn == "6671000000"
    assert result.source_text == "Свет для сцены"


@pytest.mark.asyncio
async def test_catalog_item_details_tool_adapter_returns_none_when_missing() -> None:
    adapter = CatalogItemDetailsToolAdapter(FakeDetailsUseCase(None))  # type: ignore[arg-type]

    result = await adapter.get_item_details(item_id=uuid4())

    assert result is None
