from __future__ import annotations

import pytest
from app.features.assistant.domain.action_detection import detect_action_signals
from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    EventBriefWorkflowState,
)
from app.features.assistant.router import HeuristicAssistantRouter


def test_no_rigging_event_update_is_not_direct_catalog_search() -> None:
    signals = detect_action_signals(
        "Площадка без подвеса, нужен корпоратив на 300 человек",
        BriefState(),
    )

    assert signals.event_creation is True
    assert signals.direct_catalog_search is False
    assert signals.contextual_brief_update is False


@pytest.mark.asyncio
async def test_no_rigging_event_update_updates_brief_without_search() -> None:
    decision = await HeuristicAssistantRouter().route(
        message="Площадка без подвеса, нужен корпоратив на 300 человек",
        brief=BriefState(),
    )

    inferred_categories = {
        need.category
        for need in decision.brief_update.service_needs
        if need.source == "policy_inferred"
    }
    assert decision.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert decision.workflow_stage == EventBriefWorkflowState.CLARIFYING
    assert decision.tool_intents == ["update_brief"]
    assert decision.should_search_now is False
    assert decision.search_requests == []
    assert decision.brief_update.venue_constraints == ["площадка без подвеса"]
    assert inferred_categories == {"сценические конструкции", "свет", "мультимедиа"}
    assert decision.brief_update.required_services == []
    assert decision.brief_update.must_have_services == []
    assert decision.brief_update.selected_item_ids == []


def test_professional_short_forms_are_direct_search_when_explicit() -> None:
    signals = detect_action_signals(
        "посмотри радики, фермы и экран в Екате",
        BriefState(),
    )

    assert signals.event_creation is False
    assert signals.direct_catalog_search is True


def test_need_service_for_event_is_direct_search_not_event_creation() -> None:
    signals = detect_action_signals(
        "Нужен ведущий на корпоратив в Екате",
        BriefState(),
    )

    assert signals.event_creation is False
    assert signals.direct_catalog_search is True


@pytest.mark.asyncio
async def test_direct_welcome_zone_search_does_not_execute_bundle_searches() -> None:
    decision = await HeuristicAssistantRouter().route(
        message="посмотри welcome-зону",
        brief=BriefState(),
    )

    assert decision.intent == "supplier_search"
    assert decision.should_search_now is True
    assert [
        request.service_category for request in decision.search_requests
    ] == ["welcome-зона"]


@pytest.mark.asyncio
async def test_must_have_service_satisfies_service_planning_field() -> None:
    decision = await HeuristicAssistantRouter().route(
        message=(
            "Собери бриф: корпоратив в Екате на 300 человек. "
            "Обязательно нужен звук"
        ),
        brief=BriefState(),
    )

    assert decision.intent == "brief_discovery"
    assert decision.brief_update.must_have_services == ["звук"]
    assert "required_services" not in decision.missing_fields
