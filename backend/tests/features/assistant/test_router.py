from __future__ import annotations

import pytest
from app.features.assistant.dto import BriefState
from app.features.assistant.router import HeuristicAssistantRouter


@pytest.mark.asyncio
async def test_routes_abstract_event_request_to_brief_discovery() -> None:
    decision = await HeuristicAssistantRouter().route(
        message="Хочу музыкальный вечер",
        brief=BriefState(),
    )

    assert decision.intent == "brief_discovery"
    assert decision.should_search_now is False
    assert decision.search_query is None
    assert decision.brief_update.event_type == "музыкальный вечер"
    assert "city" in decision.missing_fields
    assert "audience_size" in decision.missing_fields


@pytest.mark.asyncio
async def test_routes_concrete_equipment_request_to_supplier_search() -> None:
    decision = await HeuristicAssistantRouter().route(
        message="Нужно музыкальное оборудование в концертный зал",
        brief=BriefState(),
    )

    assert decision.intent == "supplier_search"
    assert decision.should_search_now is True
    assert decision.search_query == "музыкальное оборудование в концертный зал"
    assert decision.brief_update.required_services == ["музыкальное оборудование"]


@pytest.mark.asyncio
async def test_routes_event_request_with_planning_help_to_brief_workspace() -> None:
    decision = await HeuristicAssistantRouter().route(
        message=(
            "Организовать музыкальный вечер на 100 человек, "
            "помоги понять что нужно"
        ),
        brief=BriefState(),
    )

    assert decision.intent == "brief_discovery"
    assert decision.should_search_now is False
    assert decision.search_query is None
    assert decision.interface_mode.value == "brief_workspace"
    assert decision.tool_intents == ["update_brief"]
    assert decision.brief_update.event_type == "музыкальный вечер"
    assert decision.brief_update.audience_size == 100
    assert decision.brief_update.required_services == []


@pytest.mark.asyncio
async def test_routes_unsafe_or_too_short_message_to_clarification() -> None:
    decision = await HeuristicAssistantRouter().route(
        message="подскажи",
        brief=BriefState(),
    )

    assert decision.intent == "clarification"
    assert decision.should_search_now is False
    assert decision.search_query is None
    assert decision.missing_fields != []
