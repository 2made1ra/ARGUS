from __future__ import annotations

import json
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from app.features.assistant.dto import (
    BriefState,
    ChatTurn,
    ServiceNeed,
    VisibleCandidate,
)
from app.features.assistant.router import HeuristicAssistantRouter

FIXTURE_PATH = (
    Path(__file__).parents[2] / "fixtures" / "assistant_workflow_cases.json"
)

REQUIRED_CASE_FIELDS = {
    "message",
    "brief_before",
    "recent_turns",
    "visible_candidates",
    "candidate_item_ids",
    "expected_interface_mode",
    "expected_intent",
    "expected_workflow_stage",
    "expected_brief_patch",
    "expected_action_plan_tool_intents",
    "expected_search_categories",
    "expected_verification_targets",
    "expected_missing_fields",
}

SEED_PHRASES = {
    "Нужно организовать корпоратив на 120 человек в Екатеринбурге",
    "найди подрядчика по свету в Екатеринбурге",
    "покажи радиомикрофоны у поставщиков с НДС",
    "а что есть по свету на 300 гостей?",
    "надо закрыть welcome-зону",
    "в Екате кто сможет быстро?",
    "добавь, что площадка без подвеса, и посмотри фермы",
    "Бюджет около 2 млн, город Екатеринбург",
    "На 120 человек в Екатеринбурге нужен кейтеринг до 2500 на гостя",
    "Ок, тогда найди сцену и свет под это",
    "Площадка уже есть, монтаж только ночью",
    "Нужен звук, но без премиума, что-то рабочее",
    "проверь найденных подрядчиков",
    "проверь найденных подрядчиков, но без visible_candidates/candidate_item_ids",
    "сформируй итоговый бриф",
    "Добавь в подборку второй вариант",
    "Сравни первые два по цене",
}

INTERFACE_MODES = {"brief_workspace", "chat_search"}
WORKFLOW_STAGES = {
    "intake",
    "clarifying",
    "service_planning",
    "supplier_searching",
    "supplier_verification",
    "brief_ready",
    "brief_rendered",
    "search_clarifying",
    "searching",
    "search_results_shown",
}
INTENTS = {
    "brief_discovery",
    "brief_update",
    "clarification",
    "comparison",
    "mixed",
    "render_brief",
    "selection",
    "service_planning",
    "supplier_search",
    "verification",
}
TOOL_INTENTS = {
    "ask_clarification",
    "compare_items",
    "render_event_brief",
    "search_items",
    "select_item",
    "update_brief",
    "verify_supplier_status",
}


@dataclass(frozen=True, slots=True)
class WorkflowSnapshot:
    interface_mode: str
    intent: str
    workflow_stage: str
    brief_patch: dict[str, Any]
    tool_intents: list[str]
    search_categories: list[str]
    verification_targets: list[dict[str, str]]
    missing_fields: list[str]


class RealWorkflowRunner:
    """Runs the deterministic interpreter + policy path used by the chat router."""

    async def run(self, case: dict[str, Any]) -> WorkflowSnapshot:
        decision = await HeuristicAssistantRouter().route(
            message=case["message"],
            brief=_brief_from_fixture(case["brief_before"]),
            recent_turns=_recent_turns_from_fixture(case["recent_turns"]),
            visible_candidates=_visible_candidates_from_fixture(
                case["visible_candidates"],
            ),
            candidate_item_ids=[
                UUID(item_id) for item_id in case["candidate_item_ids"]
            ],
        )
        action_plan = decision.action_plan
        assert action_plan is not None

        return WorkflowSnapshot(
            interface_mode=decision.interface_mode.value,
            intent=decision.intent,
            workflow_stage=decision.workflow_stage.value,
            brief_patch=_brief_patch_snapshot(decision.brief_update),
            tool_intents=list(action_plan.tool_intents),
            search_categories=[
                request.service_category
                for request in action_plan.search_requests
                if request.service_category is not None
            ],
            verification_targets=[
                {"type": "item_id", "value": str(item_id)}
                for item_id in action_plan.verification_targets
            ],
            missing_fields=list(action_plan.missing_fields),
        )


def _brief_from_fixture(payload: dict[str, Any]) -> BriefState:
    values = dict(payload)
    values.pop("workflow_stage", None)
    if "service_needs" in values:
        values["service_needs"] = [
            _service_need_from_fixture(item) for item in values["service_needs"]
        ]
    if "selected_item_ids" in values:
        values["selected_item_ids"] = [
            UUID(item_id) for item_id in values["selected_item_ids"]
        ]
    return BriefState(**values)


def _service_need_from_fixture(payload: dict[str, Any]) -> ServiceNeed:
    values = dict(payload)
    if values.get("source") in {"user_explicit", "recent_turn_context"}:
        values["source"] = "explicit"
    return ServiceNeed(**values)


def _recent_turns_from_fixture(payload: list[dict[str, Any]]) -> list[ChatTurn]:
    return [ChatTurn(role=turn["role"], content=turn["content"]) for turn in payload]


def _visible_candidates_from_fixture(
    payload: list[dict[str, Any]],
) -> list[VisibleCandidate]:
    return [
        VisibleCandidate(
            ordinal=item["ordinal"],
            item_id=UUID(item["item_id"]),
            service_category=item.get("service_category"),
        )
        for item in payload
    ]


def _brief_patch_snapshot(brief: BriefState) -> dict[str, Any]:
    snapshot = _dataclass_snapshot(brief)
    snapshot.pop("open_questions", None)
    return snapshot


def _dataclass_snapshot(value: Any) -> Any:
    if is_dataclass(value):
        result: dict[str, Any] = {}
        for item in fields(value):
            field_value = getattr(value, item.name)
            if _is_empty(field_value):
                continue
            result[item.name] = _dataclass_snapshot(field_value)
        return result
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_dataclass_snapshot(item) for item in value]
    return value


def _is_empty(value: Any) -> bool:
    return value is None or value == [] or value == {}


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _cases() -> list[dict[str, Any]]:
    fixture = _load_fixture()
    cases = fixture["cases"]
    assert isinstance(cases, list)
    return cases


def _case_params() -> list[pytest.ParameterSet]:
    return [pytest.param(case, id=case["id"]) for case in _cases()]


def test_workflow_fixture_has_expected_dataset_metadata() -> None:
    fixture = _load_fixture()

    assert fixture["schema_version"] == 1
    assert "deterministic" in fixture["description"].lower()
    assert "integration_point" in fixture
    assert 25 <= len(fixture["cases"]) <= 40


def test_workflow_fixture_covers_required_seed_phrases() -> None:
    messages = {case["message"] for case in _cases()}

    assert SEED_PHRASES <= messages


def test_workflow_fixture_marks_both_interface_modes() -> None:
    modes = {case["expected_interface_mode"] for case in _cases()}
    groups = {case["case_group"] for case in _cases()}

    assert modes == INTERFACE_MODES
    assert groups == INTERFACE_MODES


@pytest.mark.parametrize("case", _case_params())
def test_workflow_case_shape(case: dict[str, Any]) -> None:
    assert REQUIRED_CASE_FIELDS <= set(case)
    assert case["case_group"] == case["expected_interface_mode"]
    assert case["expected_interface_mode"] in INTERFACE_MODES
    assert case["expected_intent"] in INTENTS
    assert case["expected_workflow_stage"] in WORKFLOW_STAGES
    assert case["message"].strip()

    assert isinstance(case["brief_before"], dict)
    assert isinstance(case["recent_turns"], list)
    assert isinstance(case["visible_candidates"], list)
    assert isinstance(case["candidate_item_ids"], list)
    assert isinstance(case["expected_brief_patch"], dict)
    assert isinstance(case["expected_action_plan_tool_intents"], list)
    assert isinstance(case["expected_search_categories"], list)
    assert isinstance(case["expected_verification_targets"], list)
    assert isinstance(case["expected_missing_fields"], list)


@pytest.mark.parametrize("case", _case_params())
def test_workflow_case_context_shape(case: dict[str, Any]) -> None:
    for turn in case["recent_turns"]:
        assert turn["role"] in {"assistant", "user"}
        assert isinstance(turn["content"], str)
        assert turn["content"].strip()

    for visible_candidate in case["visible_candidates"]:
        assert isinstance(visible_candidate["ordinal"], int)
        assert visible_candidate["ordinal"] > 0
        assert isinstance(visible_candidate["item_id"], str)
        assert visible_candidate["item_id"].strip()
        assert isinstance(visible_candidate["service_category"], str)
        assert visible_candidate["service_category"].strip()

    for candidate_item_id in case["candidate_item_ids"]:
        assert isinstance(candidate_item_id, str)
        assert candidate_item_id.strip()


@pytest.mark.parametrize("case", _case_params())
def test_workflow_case_expected_tool_contract(case: dict[str, Any]) -> None:
    tool_intents = case["expected_action_plan_tool_intents"]

    assert set(tool_intents) <= TOOL_INTENTS
    assert "call_llm" not in tool_intents

    if "search_items" in tool_intents and not case.get("expected_categoryless_search"):
        assert case["expected_search_categories"]
    else:
        assert case["expected_search_categories"] == []

    if "verify_supplier_status" in tool_intents:
        assert case["expected_verification_targets"]

    if "render_event_brief" in tool_intents:
        assert case["expected_workflow_stage"] == "brief_rendered"

    if "select_item" in tool_intents:
        assert case["visible_candidates"]

    if "compare_items" in tool_intents:
        assert len(case["visible_candidates"]) >= 2


@pytest.mark.parametrize("case", _case_params())
def test_workflow_case_expected_verification_targets_shape(
    case: dict[str, Any],
) -> None:
    for target in case["expected_verification_targets"]:
        assert set(target) == {"type", "value"}
        assert target["type"] == "item_id"
        assert target["value"].strip()


@pytest.mark.parametrize("case", _case_params())
@pytest.mark.asyncio
async def test_golden_workflow_case_matches_real_orchestrator_contract(
    case: dict[str, Any],
) -> None:
    snapshot = await RealWorkflowRunner().run(case)

    assert snapshot.interface_mode == case["expected_interface_mode"]
    assert snapshot.intent == case["expected_intent"]
    assert snapshot.workflow_stage == case["expected_workflow_stage"]
    assert snapshot.brief_patch == case["expected_brief_patch"]
    assert snapshot.tool_intents == case["expected_action_plan_tool_intents"]
    assert snapshot.search_categories == case["expected_search_categories"]
    assert snapshot.verification_targets == case["expected_verification_targets"]
    assert snapshot.missing_fields == case["expected_missing_fields"]
