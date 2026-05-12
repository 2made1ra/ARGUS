from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from app.features.assistant.domain.tool_executor import ToolExecutor
from app.features.assistant.dto import (
    ActionPlan,
    AssistantInterfaceMode,
    BriefState,
    CatalogItemDetail,
    CatalogSearchFilters,
    EventBriefWorkflowState,
    FoundCatalogItem,
    MatchReason,
    RenderedEventBrief,
    SearchRequest,
)


class FakeCatalogSearchTool:
    def __init__(self, items: list[FoundCatalogItem] | None = None) -> None:
        self.items = items if items is not None else []
        self.calls: list[dict[str, object]] = []

    async def search_items(
        self,
        *,
        query: str,
        limit: int,
        filters: CatalogSearchFilters | None = None,
    ) -> list[FoundCatalogItem]:
        self.calls.append({"query": query, "limit": limit, "filters": filters})
        return list(self.items)


class FakeCatalogItemDetailsTool:
    def __init__(self, details: dict[UUID, CatalogItemDetail]) -> None:
        self.details = details
        self.calls: list[UUID] = []

    async def get_item_details(self, *, item_id: UUID) -> CatalogItemDetail | None:
        self.calls.append(item_id)
        return self.details.get(item_id)


class FakeBriefRenderer:
    def __init__(self) -> None:
        self.calls = 0

    def render(
        self,
        *,
        brief: BriefState,
        selected_items: list[CatalogItemDetail],
        verification_results: list[object],
    ) -> RenderedEventBrief:
        self.calls += 1
        return RenderedEventBrief(
            title="Бриф мероприятия",
            sections=[],
            open_questions=list(brief.open_questions),
            evidence={"selected_item_ids": [], "verification_result_ids": []},
        )


def _found_item(item_id: UUID) -> FoundCatalogItem:
    return FoundCatalogItem(
        id=item_id,
        score=0.82,
        name="Аренда света",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО НИКА",
        supplier_city="Екатеринбург",
        source_text_snippet="Световой комплект",
        source_text_full_available=True,
        match_reason=MatchReason(
            code="semantic",
            label="Семантическое совпадение с запросом",
        ),
    )


def _detail(
    item_id: UUID,
    *,
    supplier_inn: str | None = "7701234567",
) -> CatalogItemDetail:
    return CatalogItemDetail(
        id=item_id,
        name="Аренда света",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО НИКА",
        supplier_inn=supplier_inn,
        supplier_city="Екатеринбург",
        supplier_phone=None,
        supplier_email=None,
        supplier_status=None,
        source_text="Световой комплект",
    )


@pytest.mark.asyncio
async def test_tool_executor_uses_action_plan_intents_and_caps_tool_calls() -> None:
    item_id = UUID("11111111-1111-1111-1111-111111111111")
    search = FakeCatalogSearchTool(items=[_found_item(item_id)])
    details = FakeCatalogItemDetailsTool(details={})
    renderer = FakeBriefRenderer()
    executor = ToolExecutor(
        catalog_search=search,
        item_details=details,
        brief_renderer=renderer,
        max_tool_calls_per_turn=3,
    )
    plan = ActionPlan(
        interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
        workflow_stage=EventBriefWorkflowState.SUPPLIER_SEARCHING,
        tool_intents=["update_brief", "search_items", "render_event_brief"],
        search_requests=[
            SearchRequest(query="свет", service_category="свет", limit=8),
            SearchRequest(query="звук", service_category="звук", limit=8),
            SearchRequest(query="декор", service_category="декор", limit=8),
        ],
        render_requested=True,
    )

    results = await executor.execute(
        action_plan=plan,
        brief=BriefState(),
        brief_update=BriefState(city="Екатеринбург"),
    )

    assert results.brief.city == "Екатеринбург"
    assert search.calls == [
        {"query": "свет", "limit": 8, "filters": CatalogSearchFilters()},
        {"query": "звук", "limit": 8, "filters": CatalogSearchFilters()},
        {"query": "декор", "limit": 8, "filters": CatalogSearchFilters()},
    ]
    assert len(results.found_items) == 1
    assert results.found_items[0].matched_service_categories == [
        "свет",
        "звук",
        "декор",
    ]
    assert results.rendered_brief is None
    assert renderer.calls == 0
    assert "tool_call_limit_reached:render_event_brief" in results.skipped_actions


@pytest.mark.asyncio
async def test_tool_executor_ignores_search_requests_without_approved_intent() -> None:
    search = FakeCatalogSearchTool()
    executor = ToolExecutor(
        catalog_search=search,
        item_details=FakeCatalogItemDetailsTool(details={}),
    )
    plan = ActionPlan(
        interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
        workflow_stage=EventBriefWorkflowState.SEARCHING,
        tool_intents=[],
        search_requests=[SearchRequest(query="свет", service_category="свет")],
    )

    results = await executor.execute(
        action_plan=plan,
        brief=BriefState(),
        brief_update=BriefState(city="Екатеринбург"),
    )

    assert results.brief.city is None
    assert results.found_items == []
    assert search.calls == []


@pytest.mark.asyncio
async def test_tool_executor_loads_item_details_only_for_explicit_detail_tool() -> None:
    item_id = UUID("22222222-2222-2222-2222-222222222222")
    detail = _detail(item_id)
    details = FakeCatalogItemDetailsTool(details={item_id: detail})
    executor = ToolExecutor(
        catalog_search=FakeCatalogSearchTool(),
        item_details=details,
    )
    plan = ActionPlan(
        interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
        workflow_stage=EventBriefWorkflowState.SEARCH_RESULTS_SHOWN,
        tool_intents=["get_item_details"],
        item_detail_ids=[item_id],
    )

    results = await executor.execute(
        action_plan=plan,
        brief=BriefState(),
        brief_update=BriefState(),
    )

    assert details.calls == [item_id]
    assert results.item_details == [detail]
