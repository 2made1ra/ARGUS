from __future__ import annotations

import re
from uuid import UUID

from app.features.assistant.brief import merge_brief
from app.features.assistant.dto import (
    ActionPlan,
    AssistantInterfaceMode,
    BriefState,
    EventBriefWorkflowState,
    Interpretation,
    SearchRequest,
)

_INTAKE_FIELD_ORDER = (
    "date_or_period",
    "city",
    "audience_size",
    "venue_status",
    "budget_total",
    "concept",
    "required_services",
)

_INTAKE_QUESTIONS = {
    "date_or_period": "На какую дату или период планируется мероприятие?",
    "city": "В каком городе пройдет мероприятие?",
    "audience_size": "На сколько гостей рассчитываем мероприятие?",
    "venue_status": "Площадка уже есть или ее нужно подобрать?",
    "budget_total": "Какой ориентир по общему бюджету или уровню мероприятия?",
    "concept": "Есть ли концепция или желаемый уровень мероприятия?",
    "required_services": "Какие блоки услуг нужно закрыть в первую очередь?",
}

_SEARCH_QUESTIONS = {
    "service_category": "Какую услугу или категорию нужно найти?",
    "city": "В каком городе искать подрядчика или позицию каталога?",
}

_VERIFICATION_QUESTIONS = {
    "candidate_context": (
        "Каких найденных подрядчиков проверить? Передайте выбранные позиции, "
        "candidate_item_ids, visible_candidates или явные item id."
    ),
}

_SELECTION_QUESTIONS = {
    "candidate_context": (
        "Какой вариант добавить? Выберите позицию из карточек или передайте "
        "visible_candidates с ordinal и item_id."
    ),
}

_COMPARISON_QUESTIONS = {
    "candidate_context": (
        "Какие две позиции сравнить? Передайте visible_candidates с ordinal и "
        "item_id или candidate_item_ids для видимых карточек."
    ),
}

_RENDER_QUESTIONS = {
    "brief_context": (
        "Сначала зафиксируйте хотя бы тип мероприятия, город или количество гостей."
    ),
}

_BRIEF_LOCKED_QUESTION = (
    "Сейчас идёт составление брифа. "
    "Попросите «сформируй бриф», чтобы завершить, "
    "или сбросьте бриф для нового поиска."
)


class BriefWorkflowPolicy:
    def plan(self, *, interpretation: Interpretation, brief: BriefState) -> ActionPlan:
        if interpretation.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE:
            return _brief_workspace_plan(interpretation=interpretation, brief=brief)
        if _has_renderable_brief(brief):
            return _brief_locked_plan()
        return _chat_search_plan(interpretation=interpretation)


def missing_event_intake_fields(brief: BriefState) -> list[str]:
    missing: list[str] = []
    for field_name in _INTAKE_FIELD_ORDER:
        if field_name == "budget_total":
            if (
                brief.budget_total is None
                and brief.budget_per_guest is None
                and brief.budget_notes is None
            ):
                missing.append(field_name)
            continue
        if field_name == "concept":
            if brief.concept is None and brief.event_level is None:
                missing.append(field_name)
            continue
        if field_name == "required_services":
            if not _has_explicit_service_planning(brief):
                missing.append(field_name)
            continue
        value = getattr(brief, field_name)
        if value is None or value == []:
            missing.append(field_name)
    return missing


def _has_explicit_service_planning(brief: BriefState) -> bool:
    if brief.required_services or brief.must_have_services:
        return True
    return any(need.source == "explicit" for need in brief.service_needs)


def _brief_workspace_plan(
    *,
    interpretation: Interpretation,
    brief: BriefState,
) -> ActionPlan:
    if interpretation.intent == "render_brief":
        return _render_plan(interpretation=interpretation, brief=brief)

    if interpretation.intent == "verification":
        return _verification_plan(
            interpretation=interpretation,
            brief=brief,
            fallback_stage=EventBriefWorkflowState.CLARIFYING,
        )

    if interpretation.intent == "selection":
        return _selection_plan(
            interpretation=interpretation,
            fallback_stage=EventBriefWorkflowState.CLARIFYING,
        )

    if interpretation.intent == "comparison":
        return _comparison_plan(
            interpretation=interpretation,
            fallback_stage=EventBriefWorkflowState.CLARIFYING,
        )

    merged = merge_brief(brief, interpretation.brief_update)
    missing_fields = _dedupe(
        [
            *missing_event_intake_fields(merged),
            *[
                field_name
                for field_name in interpretation.missing_fields
                if _field_is_missing(field_name, merged)
            ],
        ],
    )
    tool_intents = (
        ["update_brief"]
        if "update_brief" in interpretation.requested_actions
        else []
    )
    search_requests = list(interpretation.search_requests)
    if search_requests and "search_items" in interpretation.requested_actions:
        tool_intents.append("search_items")
        missing_fields = [
            field_name
            for field_name in missing_fields
            if field_name != "required_services"
        ]

    workflow_stage = (
        EventBriefWorkflowState.SUPPLIER_SEARCHING
        if "search_items" in tool_intents
        else EventBriefWorkflowState.CLARIFYING
    )

    return ActionPlan(
        interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
        workflow_stage=workflow_stage,
        tool_intents=tool_intents,
        search_requests=search_requests if "search_items" in tool_intents else [],
        missing_fields=missing_fields,
        clarification_questions=_dedupe(
            [
                *_questions_for(missing_fields, _INTAKE_QUESTIONS),
                *interpretation.clarification_questions,
            ],
        )[:3],
    )


def _render_plan(
    *,
    interpretation: Interpretation,
    brief: BriefState,
) -> ActionPlan:
    merged = merge_brief(brief, interpretation.brief_update)
    if _has_renderable_brief(merged) and (
        "render_event_brief" in interpretation.requested_actions
    ):
        return ActionPlan(
            interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
            workflow_stage=EventBriefWorkflowState.BRIEF_RENDERED,
            tool_intents=["render_event_brief"],
            render_requested=True,
            missing_fields=missing_event_intake_fields(merged),
        )

    missing_fields = _dedupe(["brief_context", *interpretation.missing_fields])
    return ActionPlan(
        interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
        workflow_stage=EventBriefWorkflowState.CLARIFYING,
        tool_intents=[],
        render_requested=False,
        missing_fields=missing_fields,
        clarification_questions=_dedupe(
            [
                *_questions_for(missing_fields, _RENDER_QUESTIONS),
                *interpretation.clarification_questions,
            ],
        )[:3],
    )


def _brief_locked_plan() -> ActionPlan:
    return ActionPlan(
        interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
        workflow_stage=EventBriefWorkflowState.CLARIFYING,
        tool_intents=[],
        missing_fields=[],
        clarification_questions=[_BRIEF_LOCKED_QUESTION],
    )


def _chat_search_plan(interpretation: Interpretation) -> ActionPlan:
    if interpretation.intent == "render_brief":
        return ActionPlan(
            interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
            workflow_stage=EventBriefWorkflowState.CLARIFYING,
            tool_intents=[],
            render_requested=False,
            missing_fields=["brief_context"],
            clarification_questions=[_RENDER_QUESTIONS["brief_context"]],
        )

    if interpretation.intent == "verification":
        return _verification_plan(
            interpretation=interpretation,
            brief=BriefState(),
            fallback_stage=EventBriefWorkflowState.SEARCH_CLARIFYING,
        )

    if interpretation.intent == "selection":
        return _selection_plan(
            interpretation=interpretation,
            fallback_stage=EventBriefWorkflowState.SEARCH_CLARIFYING,
        )

    if interpretation.intent == "comparison":
        return _comparison_plan(
            interpretation=interpretation,
            fallback_stage=EventBriefWorkflowState.SEARCH_CLARIFYING,
        )

    search_requests = [
        request
        for request in interpretation.search_requests
        if request.service_category is not None
        or _is_categoryless_exact_search_request(request)
    ]
    missing_fields: list[str] = []
    if not search_requests:
        missing_fields.append("service_category")
        missing_fields = _dedupe([*missing_fields, *interpretation.missing_fields])

    should_search = not missing_fields and bool(search_requests)
    return ActionPlan(
        interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
        workflow_stage=(
            EventBriefWorkflowState.SEARCHING
            if should_search
            else EventBriefWorkflowState.SEARCH_CLARIFYING
        ),
        tool_intents=["search_items"] if should_search else [],
        search_requests=search_requests if should_search else [],
        missing_fields=missing_fields,
        clarification_questions=_dedupe(
            [
                *_questions_for(missing_fields, _SEARCH_QUESTIONS),
                *interpretation.clarification_questions,
            ],
        )[:3],
    )


def _is_categoryless_exact_search_request(request: SearchRequest) -> bool:
    query = request.query.strip()
    if request.service_category is not None:
        return False
    if re.fullmatch(r"\d{10}|\d{12}", query):
        return True
    return (
        re.search(r"\b(?:ооо|ао|ано|ип|зао|пао)\b", query, flags=re.IGNORECASE)
        is not None
    )


def _verification_plan(
    *,
    interpretation: Interpretation,
    brief: BriefState,
    fallback_stage: EventBriefWorkflowState,
) -> ActionPlan:
    verification_targets = _dedupe_uuid(
        [
            *brief.selected_item_ids,
            *interpretation.verification_targets,
        ],
    )
    has_context = bool(verification_targets)
    if has_context and "verify_supplier_status" in interpretation.requested_actions:
        return ActionPlan(
            interface_mode=interpretation.interface_mode,
            workflow_stage=EventBriefWorkflowState.SUPPLIER_VERIFICATION,
            tool_intents=["verify_supplier_status"],
            verification_targets=verification_targets,
        )

    missing_fields = _dedupe(["candidate_context", *interpretation.missing_fields])
    return ActionPlan(
        interface_mode=interpretation.interface_mode,
        workflow_stage=fallback_stage,
        tool_intents=[],
        verification_targets=[],
        missing_fields=missing_fields,
        clarification_questions=_dedupe(
            [
                *_questions_for(missing_fields, _VERIFICATION_QUESTIONS),
                *interpretation.clarification_questions,
            ],
        )[:3],
    )


def _selection_plan(
    *,
    interpretation: Interpretation,
    fallback_stage: EventBriefWorkflowState,
) -> ActionPlan:
    if (
        interpretation.brief_update.selected_item_ids
        and "select_item" in interpretation.requested_actions
    ):
        return ActionPlan(
            interface_mode=interpretation.interface_mode,
            workflow_stage=EventBriefWorkflowState.SUPPLIER_SEARCHING,
            tool_intents=["select_item"],
        )

    missing_fields = _dedupe(["candidate_context", *interpretation.missing_fields])
    return ActionPlan(
        interface_mode=interpretation.interface_mode,
        workflow_stage=fallback_stage,
        tool_intents=[],
        missing_fields=missing_fields,
        clarification_questions=_dedupe(
            [
                *_questions_for(missing_fields, _SELECTION_QUESTIONS),
                *interpretation.clarification_questions,
            ],
        )[:3],
    )


def _comparison_plan(
    *,
    interpretation: Interpretation,
    fallback_stage: EventBriefWorkflowState,
) -> ActionPlan:
    if "compare_items" in interpretation.requested_actions:
        return ActionPlan(
            interface_mode=interpretation.interface_mode,
            workflow_stage=EventBriefWorkflowState.SEARCH_RESULTS_SHOWN,
            tool_intents=["compare_items"],
            comparison_targets=list(interpretation.comparison_targets),
        )

    missing_fields = _dedupe(["candidate_context", *interpretation.missing_fields])
    return ActionPlan(
        interface_mode=interpretation.interface_mode,
        workflow_stage=fallback_stage,
        tool_intents=[],
        missing_fields=missing_fields,
        clarification_questions=_dedupe(
            [
                *_questions_for(missing_fields, _COMPARISON_QUESTIONS),
                *interpretation.clarification_questions,
            ],
        )[:3],
    )


def _questions_for(
    missing_fields: list[str],
    question_map: dict[str, str],
) -> list[str]:
    return [
        question_map[field]
        for field in missing_fields[:3]
        if field in question_map
    ]


def _field_is_missing(field_name: str, brief: BriefState) -> bool:
    if not hasattr(brief, field_name):
        return True
    if field_name == "budget_total":
        return (
            brief.budget_total is None
            and brief.budget_per_guest is None
            and brief.budget_notes is None
        )
    if field_name == "concept":
        return brief.concept is None and brief.event_level is None
    value = getattr(brief, field_name)
    return value is None or value == []


def _has_renderable_brief(brief: BriefState) -> bool:
    return any(
        (
            brief.event_type,
            brief.event_goal,
            brief.concept,
            brief.format,
            brief.city,
            brief.date_or_period,
            brief.audience_size,
            brief.venue,
            brief.venue_status,
            brief.venue_constraints,
            brief.duration_or_time_window,
            brief.event_level,
            brief.budget_total,
            brief.budget_per_guest,
            brief.budget_notes,
            brief.service_needs,
            brief.required_services,
            brief.must_have_services,
            brief.nice_to_have_services,
            brief.selected_item_ids,
            brief.constraints,
            brief.preferences,
        )
    )


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def _dedupe_uuid(values: list[UUID]) -> list[UUID]:
    result: list[UUID] = []
    seen: set[UUID] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


__all__ = ["BriefWorkflowPolicy", "missing_event_intake_fields"]
