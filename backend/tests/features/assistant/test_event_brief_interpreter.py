from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from app.features.assistant.domain.brief_workflow_policy import BriefWorkflowPolicy
from app.features.assistant.domain.event_brief_interpreter import EventBriefInterpreter
from app.features.assistant.domain.llm_router import validate_llm_router_json
from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    ChatTurn,
    VisibleCandidate,
)


@dataclass(slots=True)
class FakeLLMStructuredRouter:
    output: str
    calls: list[Any]

    async def route_structured(self, *, prompt: Any) -> str:
        self.calls.append(prompt)
        return self.output


@pytest.mark.asyncio
async def test_llm_enriches_direct_search_without_authorizing_tools() -> None:
    llm = FakeLLMStructuredRouter(
        output="""{
            "interface_mode": "chat_search",
            "intent": "supplier_search",
            "confidence": 0.91,
            "tool_intents": ["search_items"],
            "search_requests": [
                {
                    "query": "световое оборудование Екатеринбург",
                    "service_category": "свет",
                    "filters": {
                        "supplier_city_normalized": "екатеринбург",
                        "unexpected_filter": "drop"
                    },
                    "priority": 1,
                    "limit": 6
                }
            ],
            "missing_fields": ["city"],
            "clarification_questions": ["Нужен монтаж или только аренда?"],
            "user_visible_summary": "Похоже, нужен поиск по свету."
        }""",
        calls=[],
    )
    visible_item_id = UUID("11111111-1111-1111-1111-111111111111")

    interpretation = await EventBriefInterpreter(llm_router=llm).interpret_with_llm(
        message="найди подрядчика в Екатеринбурге",
        brief=BriefState(),
        recent_turns=[ChatTurn(role="user", content="Ищу технического подрядчика")],
        visible_candidates=[
            VisibleCandidate(
                ordinal=1,
                item_id=visible_item_id,
                service_category="звук",
            ),
        ],
    )

    assert llm.calls
    prompt_text = "\n".join(message.content for message in llm.calls[0].messages)
    assert "найди подрядчика в Екатеринбурге" in prompt_text
    assert "Ищу технического подрядчика" in prompt_text
    assert str(visible_item_id) in prompt_text
    assert "allowed_interface_modes" in prompt_text
    assert "allowed_intents" in prompt_text
    assert "allowed_tool_intents" in prompt_text
    assert "strict_json_schema" in prompt_text

    assert interpretation.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert interpretation.requested_actions == ["search_items"]
    assert interpretation.search_requests[0].service_category == "свет"
    assert interpretation.search_requests[0].limit == 6
    assert (
        interpretation.search_requests[0].filters.supplier_city_normalized
        == "екатеринбург"
    )
    assert "llm_router_used" in interpretation.reason_codes
    assert interpretation.user_visible_summary == "Похоже, нужен поиск по свету."

    plan = BriefWorkflowPolicy().plan(
        interpretation=interpretation,
        brief=BriefState(),
    )

    assert plan.should_search_now is True
    assert plan.tool_intents == ["search_items"]
    assert "city" not in plan.missing_fields


@pytest.mark.asyncio
async def test_deterministic_brief_facts_win_over_llm_conflicts() -> None:
    llm = FakeLLMStructuredRouter(
        output="""{
            "interface_mode": "chat_search",
            "intent": "supplier_search",
            "confidence": 0.93,
            "brief_update": {
                "event_type": "конференция",
                "city": "Москва",
                "audience_size": 999,
                "selected_item_ids": ["22222222-2222-2222-2222-222222222222"]
            },
            "search_requests": [
                {"query": "кейтеринг Москва", "service_category": "кейтеринг"}
            ]
        }""",
        calls=[],
    )

    interpretation = await EventBriefInterpreter(llm_router=llm).interpret_with_llm(
        message="Нужно организовать корпоратив на 120 человек в Екатеринбурге",
        brief=BriefState(),
        recent_turns=[],
        visible_candidates=[],
    )

    assert interpretation.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert interpretation.intent == "brief_discovery"
    assert interpretation.brief_update.event_type == "корпоратив"
    assert interpretation.brief_update.city == "Екатеринбург"
    assert interpretation.brief_update.audience_size == 120
    assert interpretation.brief_update.selected_item_ids == []
    assert interpretation.requested_actions == ["update_brief"]
    assert interpretation.search_requests == []
    assert "llm_conflict_resolved" in interpretation.reason_codes


@pytest.mark.asyncio
async def test_llm_brief_update_does_not_create_unchecked_facts() -> None:
    llm = FakeLLMStructuredRouter(
        output="""{
            "interface_mode": "brief_workspace",
            "intent": "brief_discovery",
            "confidence": 0.92,
            "brief_update": {
                "event_type": "корпоратив",
                "city": "Москва",
                "audience_size": 999
            }
        }""",
        calls=[],
    )

    interpretation = await EventBriefInterpreter(llm_router=llm).interpret_with_llm(
        message="корпоратив в Екатеринбурге",
        brief=BriefState(),
        recent_turns=[],
        visible_candidates=[],
    )

    assert interpretation.brief_update == BriefState()
    assert interpretation.requested_actions == []
    assert "llm_conflict_resolved" in interpretation.reason_codes


@pytest.mark.asyncio
async def test_direct_search_stays_chat_search_when_llm_opens_workspace() -> None:
    llm = FakeLLMStructuredRouter(
        output="""{
            "interface_mode": "brief_workspace",
            "intent": "brief_discovery",
            "confidence": 0.9,
            "brief_update": {"event_type": "корпоратив"}
        }""",
        calls=[],
    )

    interpretation = await EventBriefInterpreter(llm_router=llm).interpret_with_llm(
        message="найди подрядчика по свету в Екатеринбурге",
        brief=BriefState(),
        recent_turns=[],
        visible_candidates=[],
    )

    assert interpretation.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert interpretation.intent == "supplier_search"
    assert interpretation.brief_update.event_type is None
    assert "llm_conflict_resolved" in interpretation.reason_codes


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["not-json", '{"confidence": 0.54}'])
async def test_invalid_or_low_confidence_llm_output_falls_back_to_deterministic(
    output: str,
) -> None:
    llm = FakeLLMStructuredRouter(output=output, calls=[])

    interpretation = await EventBriefInterpreter(llm_router=llm).interpret_with_llm(
        message="найди подрядчика по свету в Екатеринбурге",
        brief=BriefState(),
        recent_turns=[],
        visible_candidates=[],
    )

    assert interpretation.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert interpretation.intent == "supplier_search"
    assert interpretation.search_requests[0].service_category == "свет"
    assert "llm_router_fallback_used" in interpretation.reason_codes


def test_llm_validation_clamps_confidence_and_drops_unknown_values() -> None:
    result = validate_llm_router_json(
        """{
            "interface_mode": "admin_panel",
            "intent": "run_sql",
            "confidence": 1.7,
            "tool_intents": ["search_items", "write_sql"],
            "search_requests": [
                {
                    "query": "радиомикрофоны",
                    "service_category": "звук",
                    "filters": {
                        "vat_mode": "with_vat",
                        "raw_sql": "select * from price_items"
                    },
                    "priority": 2,
                    "limit": 12
                }
            ],
            "unknown_top_level": "drop"
        }""",
    )

    assert result is not None
    assert result.interface_mode is None
    assert result.intent is None
    assert result.confidence == 1.0
    assert result.tool_intents == ["search_items"]
    assert result.search_requests[0].filters.vat_mode == "with_vat"
    assert not hasattr(result.search_requests[0].filters, "raw_sql")
