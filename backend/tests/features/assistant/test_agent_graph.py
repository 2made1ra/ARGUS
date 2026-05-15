from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.features.assistant.agent_graph import (
    AssistantAgentPlan,
    AssistantGraphRunner,
    ProposedToolCall,
)
from app.features.assistant.dto import (
    AssistantChatRequest,
    AssistantInterfaceMode,
    BriefState,
    CatalogItemDetail,
    CatalogSearchFilters,
    EventBriefWorkflowState,
    FoundCatalogItem,
    MatchReason,
    SearchRequest,
    SupplierVerificationResult,
)


class FakePlanner:
    def __init__(self, plans: list[AssistantAgentPlan]) -> None:
        self._plans = plans
        self.calls: list[dict[str, Any]] = []

    async def plan(self, state: dict[str, Any]) -> AssistantAgentPlan:
        self.calls.append(state)
        if not self._plans:
            return AssistantAgentPlan()
        return self._plans.pop(0)


class FakeCatalogSearchTool:
    def __init__(self, items: list[FoundCatalogItem] | None = None) -> None:
        self.items = items if items is not None else []
        self.calls: list[dict[str, Any]] = []

    async def search_items(
        self,
        *,
        query: str,
        limit: int,
        filters: CatalogSearchFilters | None = None,
    ) -> list[FoundCatalogItem]:
        self.calls.append({"query": query, "limit": limit, "filters": filters})
        return self.items


class FakeCatalogItemDetailsTool:
    def __init__(self, details: dict[UUID, CatalogItemDetail]) -> None:
        self.details = details
        self.calls: list[UUID] = []

    async def get_item_details(self, *, item_id: UUID) -> CatalogItemDetail | None:
        self.calls.append(item_id)
        return self.details.get(item_id)


class FakeSupplierVerificationTool:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    async def verify_by_inn_or_ogrn(
        self,
        *,
        inn: str | None,
        ogrn: str | None,
        supplier_name: str | None,
    ) -> SupplierVerificationResult:
        self.calls.append(
            {"inn": inn, "ogrn": ogrn, "supplier_name": supplier_name},
        )
        return SupplierVerificationResult(
            item_id=None,
            supplier_name=supplier_name,
            supplier_inn=inn,
            ogrn=ogrn,
            legal_name=supplier_name,
            status="active",
            source="fake",
            checked_at=None,
        )


def _found_item() -> FoundCatalogItem:
    return FoundCatalogItem(
        id=uuid4(),
        score=0.91,
        name="Световой комплект",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО Свет",
        supplier_city="Екатеринбург",
        source_text_snippet="Световой комплект для сцены",
        source_text_full_available=True,
        match_reason=MatchReason(
            code="semantic",
            label="Семантическое совпадение с запросом",
        ),
    )


def _item_detail(item_id: UUID, *, inn: str | None = "6671000000") -> CatalogItemDetail:
    return CatalogItemDetail(
        id=item_id,
        name="Световой комплект",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО Свет",
        supplier_inn=inn,
        supplier_city="Екатеринбург",
        supplier_phone=None,
        supplier_email=None,
        supplier_status="active",
        source_text="Световой комплект для сцены",
    )


@pytest.mark.asyncio
async def test_agent_graph_executes_valid_search_tool_call() -> None:
    item = _found_item()
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
                workflow_stage=EventBriefWorkflowState.SEARCHING,
                tool_calls=[
                    ProposedToolCall(
                        name="search_items",
                        args={"query": "свет екатеринбург", "limit": 5},
                    ),
                ],
            ),
            AssistantAgentPlan(
                interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
                workflow_stage=EventBriefWorkflowState.SEARCH_RESULTS_SHOWN,
                message="Нашел подходящие позиции.",
            ),
        ],
    )
    search = FakeCatalogSearchTool([item])
    runner = AssistantGraphRunner(
        planner=planner,
        catalog_search=search,
        max_tool_calls_per_turn=3,
        max_iterations=3,
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=UUID("11111111-1111-1111-1111-111111111111"),
            message="Найди свет в Екатеринбурге",
            brief=BriefState(),
        ),
    )

    assert response.session_id == UUID("11111111-1111-1111-1111-111111111111")
    assert response.ui_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert response.action_plan is not None
    assert response.action_plan.tool_intents == ["search_items"]
    assert response.action_plan.skipped_actions == []
    assert response.found_items == [item]
    assert response.router.search_requests == [
        SearchRequest(query="свет екатеринбург", limit=5),
    ]
    assert search.calls == [
        {"query": "свет екатеринбург", "limit": 5, "filters": CatalogSearchFilters()},
    ]
    assert len(planner.calls) == 2
    assert planner.calls[1]["found_items"] == [item]


@pytest.mark.asyncio
async def test_agent_graph_skips_unknown_tool_without_calling_backend() -> None:
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                tool_calls=[
                    ProposedToolCall(
                        name="run_sql",
                        args={"query": "drop table price_items"},
                    ),
                ],
            ),
            AssistantAgentPlan(message="Не могу выполнить этот инструмент."),
        ],
    )
    search = FakeCatalogSearchTool()
    runner = AssistantGraphRunner(
        planner=planner,
        catalog_search=search,
        max_tool_calls_per_turn=3,
        max_iterations=3,
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="выполни SQL",
            brief=BriefState(),
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.tool_intents == []
    assert response.action_plan.skipped_actions == ["unsupported_tool:run_sql"]
    assert response.found_items == []
    assert search.calls == []


@pytest.mark.asyncio
async def test_agent_graph_enforces_tool_call_budget() -> None:
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                tool_calls=[
                    ProposedToolCall(
                        name="search_items",
                        args={"query": "свет", "limit": 3},
                    ),
                    ProposedToolCall(
                        name="search_items",
                        args={"query": "звук", "limit": 3},
                    ),
                ],
            ),
            AssistantAgentPlan(message="Показал доступные результаты."),
        ],
    )
    search = FakeCatalogSearchTool([_found_item()])
    runner = AssistantGraphRunner(
        planner=planner,
        catalog_search=search,
        max_tool_calls_per_turn=1,
        max_iterations=3,
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="Найди свет и звук",
            brief=BriefState(),
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.tool_intents == ["search_items"]
    assert response.action_plan.skipped_actions == [
        "tool_call_limit_reached:search_items",
    ]
    assert search.calls == [
        {"query": "свет", "limit": 3, "filters": CatalogSearchFilters()},
    ]


@pytest.mark.asyncio
async def test_agent_graph_enforces_tool_call_budget_across_iterations() -> None:
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                tool_calls=[
                    ProposedToolCall(
                        name="search_items",
                        args={"query": "свет", "limit": 3},
                    ),
                ],
            ),
            AssistantAgentPlan(
                tool_calls=[
                    ProposedToolCall(
                        name="search_items",
                        args={"query": "звук", "limit": 3},
                    ),
                ],
            ),
        ],
    )
    search = FakeCatalogSearchTool([_found_item()])
    runner = AssistantGraphRunner(
        planner=planner,
        catalog_search=search,
        max_tool_calls_per_turn=1,
        max_iterations=3,
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="Найди свет и звук",
            brief=BriefState(),
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.skipped_actions == [
        "tool_call_limit_reached:search_items",
    ]
    assert search.calls == [
        {"query": "свет", "limit": 3, "filters": CatalogSearchFilters()},
    ]


@pytest.mark.asyncio
async def test_agent_graph_preserves_structured_search_filters() -> None:
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                tool_calls=[
                    ProposedToolCall(
                        name="search_items",
                        args={
                            "query": "радиомикрофон",
                            "limit": 4,
                            "service_category": "звук",
                            "filters": {
                                "supplier_city_normalized": "екатеринбург",
                                "has_vat": "yes",
                                "unit_price_min": 1000,
                                "unit_price_max": 5000,
                            },
                        },
                    ),
                ],
            ),
            AssistantAgentPlan(message="Нашел позиции."),
        ],
    )
    search = FakeCatalogSearchTool([_found_item()])
    runner = AssistantGraphRunner(
        planner=planner,
        catalog_search=search,
        max_iterations=3,
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="Найди радиомикрофон с НДС",
            brief=BriefState(),
        ),
    )

    expected_filters = CatalogSearchFilters(
        supplier_city_normalized="екатеринбург",
        service_category="звук",
        has_vat="yes",
        unit_price_min=1000,
        unit_price_max=5000,
    )
    assert response.router.search_requests == [
        SearchRequest(
            query="радиомикрофон",
            service_category="звук",
            filters=expected_filters,
            limit=4,
        ),
    ]
    assert search.calls == [
        {"query": "радиомикрофон", "limit": 4, "filters": expected_filters},
    ]


@pytest.mark.asyncio
async def test_agent_graph_executes_details_selection_verification_and_render() -> None:
    item_id = uuid4()
    details = FakeCatalogItemDetailsTool({item_id: _item_detail(item_id)})
    verifier = FakeSupplierVerificationTool()
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
                workflow_stage=EventBriefWorkflowState.SUPPLIER_VERIFICATION,
                brief_update=BriefState(event_type="Корпоратив", city="Екатеринбург"),
                tool_calls=[
                    ProposedToolCall(name="update_brief"),
                    ProposedToolCall(
                        name="select_item",
                        args={"item_id": str(item_id)},
                    ),
                    ProposedToolCall(
                        name="get_item_details",
                        args={"item_id": str(item_id)},
                    ),
                    ProposedToolCall(
                        name="verify_supplier_status",
                        args={"item_ids": [str(item_id)]},
                    ),
                    ProposedToolCall(name="render_event_brief"),
                ],
            ),
            AssistantAgentPlan(
                interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
                workflow_stage=EventBriefWorkflowState.BRIEF_RENDERED,
                message="Бриф подготовлен.",
            ),
        ],
    )
    runner = AssistantGraphRunner(
        planner=planner,
        item_details=details,
        supplier_verification=verifier,
        max_tool_calls_per_turn=3,
        max_iterations=3,
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="Добавь позицию, проверь поставщика и собери бриф",
            brief=BriefState(),
            candidate_item_ids=[item_id],
        ),
    )

    assert response.brief.selected_item_ids == [item_id]
    assert response.item_details == [_item_detail(item_id)]
    assert response.verification_results[0].supplier_inn == "6671000000"
    assert response.rendered_brief is not None
    assert response.rendered_brief.evidence["selected_item_ids"] == [str(item_id)]
    assert verifier.calls == [
        {"inn": "6671000000", "ogrn": None, "supplier_name": "ООО Свет"},
    ]


@pytest.mark.asyncio
async def test_agent_graph_maps_deduped_verification_result_to_each_item() -> None:
    first_id = uuid4()
    second_id = uuid4()
    details = FakeCatalogItemDetailsTool(
        {
            first_id: _item_detail(first_id, inn="6671000000"),
            second_id: _item_detail(second_id, inn="6671000000"),
        },
    )
    verifier = FakeSupplierVerificationTool()
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                tool_calls=[
                    ProposedToolCall(
                        name="verify_supplier_status",
                        args={"item_ids": [str(first_id), str(second_id)]},
                    ),
                ],
            ),
            AssistantAgentPlan(message="Проверил поставщика."),
        ],
    )
    runner = AssistantGraphRunner(
        planner=planner,
        item_details=details,
        supplier_verification=verifier,
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="Проверь подрядчиков",
            brief=BriefState(),
            candidate_item_ids=[first_id, second_id],
        ),
    )

    assert [result.item_id for result in response.verification_results] == [
        first_id,
        second_id,
    ]
    assert verifier.calls == [
        {"inn": "6671000000", "ogrn": None, "supplier_name": "ООО Свет"},
    ]


@pytest.mark.asyncio
async def test_agent_graph_does_not_mark_known_tools_as_unsupported() -> None:
    item_id = uuid4()
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                tool_calls=[
                    ProposedToolCall(
                        name="compare_items",
                        args={"item_ids": [str(item_id)]},
                    ),
                ],
            ),
            AssistantAgentPlan(message="Сравнил позиции."),
        ],
    )
    runner = AssistantGraphRunner(
        planner=planner,
        item_details=FakeCatalogItemDetailsTool({item_id: _item_detail(item_id)}),
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="Сравни позиции",
            brief=BriefState(),
            candidate_item_ids=[item_id],
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.tool_intents == ["compare_items"]
    assert response.action_plan.skipped_actions == []
    assert response.item_details == [_item_detail(item_id)]


@pytest.mark.asyncio
async def test_agent_graph_rejects_verification_without_target_context() -> None:
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                tool_calls=[ProposedToolCall(name="verify_supplier_status")],
            ),
            AssistantAgentPlan(message="Нужно выбрать подрядчика для проверки."),
        ],
    )
    verifier = FakeSupplierVerificationTool()
    runner = AssistantGraphRunner(
        planner=planner,
        supplier_verification=verifier,
    )

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="Проверь подрядчиков",
            brief=BriefState(),
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.tool_intents == []
    assert response.action_plan.skipped_actions == ["verification_targets_missing"]
    assert response.verification_results == []
    assert verifier.calls == []


@pytest.mark.asyncio
async def test_agent_graph_rejects_selection_of_hidden_item_id() -> None:
    hidden_id = uuid4()
    planner = FakePlanner(
        [
            AssistantAgentPlan(
                tool_calls=[
                    ProposedToolCall(
                        name="select_item",
                        args={"item_id": str(hidden_id)},
                    ),
                ],
            ),
            AssistantAgentPlan(message="Нужно выбрать позицию из видимых карточек."),
        ],
    )
    runner = AssistantGraphRunner(planner=planner)

    response = await runner.execute(
        AssistantChatRequest(
            session_id=None,
            message="Выбери эту позицию",
            brief=BriefState(),
            candidate_item_ids=[uuid4()],
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.tool_intents == []
    assert response.action_plan.skipped_actions == ["invalid_tool_args:select_item"]
    assert response.brief.selected_item_ids == []
