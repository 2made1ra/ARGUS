from __future__ import annotations

from app.features.assistant.brief import merge_brief
from app.features.assistant.domain.brief_workflow_policy import BriefWorkflowPolicy
from app.features.assistant.domain.event_brief_interpreter import EventBriefInterpreter
from app.features.assistant.domain.llm_router import validate_llm_router_json
from app.features.assistant.domain.search_planning import SearchPlanner
from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    EventBriefWorkflowState,
    RouterDecision,
    SearchRequest,
)


def test_plans_service_group_searches_from_interpreted_turn() -> None:
    brief_before = BriefState()
    interpretation = EventBriefInterpreter().interpret(
        message="подбери кейтеринг и свет на 120 человек в Екатеринбурге",
        brief=brief_before,
    )
    action_plan = BriefWorkflowPolicy().plan(
        interpretation=interpretation,
        brief=brief_before,
    )
    brief_after = merge_brief(brief_before, interpretation.brief_update)
    decision = _decision(
        search_requests=action_plan.search_requests,
        workflow_stage=action_plan.workflow_stage,
    )

    planned = SearchPlanner().plan(
        decision=decision,
        brief_before=brief_before,
        brief_after=brief_after,
        workflow_stage=action_plan.workflow_stage,
    )

    assert [request.service_category for request in planned] == [
        "кейтеринг",
        "свет",
    ]
    assert [request.priority for request in planned] == [1, 2]
    assert all(
        request.filters.supplier_city_normalized == "екатеринбург"
        for request in planned
    )
    assert "кейтеринг" in planned[0].query
    assert "свет" in planned[1].query
    assert "120 человек" in planned[0].query
    assert "Екатеринбург" in planned[1].query


def test_search_query_uses_brief_context_and_budget_filter_when_useful() -> None:
    brief_before = BriefState(city="Екатеринбург")
    brief_after = BriefState(
        event_type="корпоратив",
        concept="неоновая вечеринка",
        city="Екатеринбург",
        audience_size=120,
        venue_constraints=["площадка без подвеса"],
        budget_per_guest=2500,
    )
    decision = _decision(
        search_requests=[SearchRequest(query="фуршет", service_category="кейтеринг")],
        workflow_stage=EventBriefWorkflowState.SUPPLIER_SEARCHING,
    )

    planned = SearchPlanner().plan(
        decision=decision,
        brief_before=brief_before,
        brief_after=brief_after,
        workflow_stage=EventBriefWorkflowState.SUPPLIER_SEARCHING,
    )

    assert len(planned) == 1
    request = planned[0]
    assert request.query == (
        "кейтеринг фуршет корпоратив 120 человек Екатеринбург "
        "площадка без подвеса до 2500 на гостя неоновая вечеринка"
    )
    assert request.filters.supplier_city_normalized == "екатеринбург"
    assert request.filters.unit_price_max == 2500


def test_city_filter_matches_catalog_normalization_for_prefixed_city() -> None:
    decision = _decision(
        search_requests=[SearchRequest(query="свет", service_category="свет")],
        workflow_stage=EventBriefWorkflowState.SEARCHING,
    )

    planned = SearchPlanner().plan(
        decision=decision,
        brief_before=BriefState(),
        brief_after=BriefState(city="г. Екатеринбург"),
        workflow_stage=EventBriefWorkflowState.SEARCHING,
    )

    assert planned[0].filters.supplier_city_normalized == "екатеринбург"


def test_limits_planned_searches_to_three_by_priority() -> None:
    decision = _decision(
        search_requests=[
            SearchRequest(query="звук", service_category="звук", priority=3),
            SearchRequest(query="свет", service_category="свет", priority=1),
            SearchRequest(
                query="сцена",
                service_category="сценические конструкции",
                priority=2,
            ),
            SearchRequest(query="декор", service_category="декор", priority=4),
        ],
        workflow_stage=EventBriefWorkflowState.SUPPLIER_SEARCHING,
    )

    planned = SearchPlanner().plan(
        decision=decision,
        brief_before=BriefState(),
        brief_after=BriefState(),
        workflow_stage=EventBriefWorkflowState.SUPPLIER_SEARCHING,
    )

    assert [request.service_category for request in planned] == [
        "свет",
        "сценические конструкции",
        "звук",
    ]


def test_unknown_filter_keys_are_dropped_before_planning() -> None:
    suggestion = validate_llm_router_json(
        """{
            "interface_mode": "chat_search",
            "intent": "supplier_search",
            "confidence": 0.9,
            "tool_intents": ["search_items"],
            "search_requests": [
                {
                    "query": "свет Екатеринбург",
                    "service_category": "свет",
                    "filters": {
                        "supplier_city_normalized": "екатеринбург",
                        "raw_sql": "select * from price_items",
                        "unit_price_max": 50000
                    }
                }
            ]
        }""",
    )
    assert suggestion is not None
    decision = _decision(
        search_requests=suggestion.search_requests,
        workflow_stage=EventBriefWorkflowState.SEARCHING,
    )

    planned = SearchPlanner().plan(
        decision=decision,
        brief_before=BriefState(),
        brief_after=BriefState(),
        workflow_stage=EventBriefWorkflowState.SEARCHING,
    )

    assert planned[0].filters.supplier_city_normalized == "екатеринбург"
    assert planned[0].filters.unit_price_max == 50000
    assert not hasattr(planned[0].filters, "raw_sql")


def _decision(
    *,
    search_requests: list[SearchRequest],
    workflow_stage: EventBriefWorkflowState,
) -> RouterDecision:
    return RouterDecision(
        intent="supplier_search",
        confidence=0.88,
        known_facts={},
        missing_fields=[],
        should_search_now=True,
        search_query=search_requests[0].query if search_requests else None,
        brief_update=BriefState(),
        interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
        workflow_stage=workflow_stage,
        search_requests=search_requests,
        tool_intents=["search_items"],
    )
