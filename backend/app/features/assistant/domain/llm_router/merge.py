from __future__ import annotations

from dataclasses import fields

from app.features.assistant.domain.llm_router.contract import (
    LLM_ROUTER_MIN_CONFIDENCE,
    LLMRouterSuggestion,
)
from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    CatalogSearchFilters,
    Interpretation,
    SearchRequest,
)


def merge_llm_router_suggestion(
    *,
    deterministic: Interpretation,
    suggestion: LLMRouterSuggestion,
) -> Interpretation:
    if suggestion.confidence < LLM_ROUTER_MIN_CONFIDENCE:
        return interpretation_with_reason(
            deterministic,
            "llm_router_fallback_used",
        )

    conflict_resolved = False
    reason_codes = _dedupe(
        [
            *deterministic.reason_codes,
            *suggestion.reason_codes,
            "llm_router_used",
        ],
    )
    explicit_mode = _explicit_mode_from_deterministic(deterministic)
    interface_mode = deterministic.interface_mode
    if suggestion.interface_mode is not None:
        if explicit_mode is not None and suggestion.interface_mode != explicit_mode:
            conflict_resolved = True
        elif explicit_mode is None:
            interface_mode = suggestion.interface_mode

    intent = deterministic.intent
    if suggestion.intent is not None:
        if deterministic.intent == "clarification":
            intent = suggestion.intent
        elif suggestion.intent != deterministic.intent:
            conflict_resolved = True

    brief_update = deterministic.brief_update
    if _brief_has_data(suggestion.brief_update):
        conflict_resolved = (
            conflict_resolved
            or _brief_suggestion_adds_or_conflicts(
                deterministic.brief_update,
                suggestion.brief_update,
            )
        )

    search_requests = list(deterministic.search_requests)
    if suggestion.search_requests:
        if "search_items" in deterministic.requested_actions:
            search_requests, search_conflict = _merge_search_requests(
                deterministic.search_requests,
                suggestion.search_requests,
            )
            conflict_resolved = conflict_resolved or search_conflict
        elif deterministic.intent != "clarification":
            conflict_resolved = True

    if conflict_resolved:
        reason_codes.append("llm_conflict_resolved")

    return Interpretation(
        interface_mode=interface_mode,
        intent=intent,
        confidence=max(deterministic.confidence, suggestion.confidence),
        reason_codes=_dedupe(reason_codes),
        brief_update=brief_update,
        service_needs=list(deterministic.service_needs),
        requested_actions=list(deterministic.requested_actions),
        search_requests=search_requests,
        missing_fields=_dedupe(
            [*deterministic.missing_fields, *suggestion.missing_fields],
        ),
        clarification_questions=_dedupe(
            [
                *deterministic.clarification_questions,
                *suggestion.clarification_questions,
            ],
        ),
        user_visible_summary=(
            suggestion.user_visible_summary
            if suggestion.user_visible_summary is not None
            else deterministic.user_visible_summary
        ),
    )


def interpretation_with_reason(
    interpretation: Interpretation,
    reason_code: str,
) -> Interpretation:
    return Interpretation(
        interface_mode=interpretation.interface_mode,
        intent=interpretation.intent,
        confidence=interpretation.confidence,
        reason_codes=_dedupe([*interpretation.reason_codes, reason_code]),
        brief_update=interpretation.brief_update,
        service_needs=list(interpretation.service_needs),
        requested_actions=list(interpretation.requested_actions),
        search_requests=list(interpretation.search_requests),
        missing_fields=list(interpretation.missing_fields),
        clarification_questions=list(interpretation.clarification_questions),
        user_visible_summary=interpretation.user_visible_summary,
    )


def _explicit_mode_from_deterministic(
    deterministic: Interpretation,
) -> AssistantInterfaceMode | None:
    reason_codes = set(deterministic.reason_codes)
    if "direct_catalog_search_detected" in reason_codes:
        return AssistantInterfaceMode.CHAT_SEARCH
    if reason_codes & {"event_creation_intent_detected", "brief_update_detected"}:
        return AssistantInterfaceMode.BRIEF_WORKSPACE
    return None


def _brief_has_data(brief: BriefState) -> bool:
    for field in fields(BriefState):
        value = getattr(brief, field.name)
        if value is not None and value != []:
            return True
    return False


def _brief_suggestion_adds_or_conflicts(
    deterministic: BriefState,
    llm: BriefState,
) -> bool:
    for field in fields(BriefState):
        field_name = field.name
        if field_name == "selected_item_ids":
            if llm.selected_item_ids:
                return True
            continue

        deterministic_value = getattr(deterministic, field_name)
        llm_value = getattr(llm, field_name)
        if llm_value is None or llm_value == []:
            continue
        if deterministic_value is None or deterministic_value == []:
            return True
        if llm_value != deterministic_value:
            return True
    return False


def _merge_search_requests(
    deterministic: list[SearchRequest],
    llm: list[SearchRequest],
) -> tuple[list[SearchRequest], bool]:
    if not deterministic:
        return list(llm), False

    conflict = False
    merged = list(deterministic)
    by_category = {
        request.service_category: index
        for index, request in enumerate(merged)
        if request.service_category is not None
    }
    for llm_request in llm:
        category = llm_request.service_category
        if category is not None and category in by_category:
            index = by_category[category]
            merged[index], filter_conflict = _merge_search_request(
                merged[index],
                llm_request,
            )
            conflict = conflict or filter_conflict
            continue
        merged.append(llm_request)
    return merged, conflict


def _merge_search_request(
    deterministic: SearchRequest,
    llm: SearchRequest,
) -> tuple[SearchRequest, bool]:
    filters, conflict = _merge_filters(deterministic.filters, llm.filters)
    return (
        SearchRequest(
            query=deterministic.query,
            service_category=deterministic.service_category,
            filters=filters,
            priority=deterministic.priority,
            limit=deterministic.limit,
        ),
        conflict,
    )


def _merge_filters(
    deterministic: CatalogSearchFilters,
    llm: CatalogSearchFilters,
) -> tuple[CatalogSearchFilters, bool]:
    values: dict[str, object] = {}
    conflict = False
    for field in fields(CatalogSearchFilters):
        deterministic_value = getattr(deterministic, field.name)
        llm_value = getattr(llm, field.name)
        if deterministic_value is not None:
            values[field.name] = deterministic_value
            if llm_value is not None and llm_value != deterministic_value:
                conflict = True
        else:
            values[field.name] = llm_value
    return CatalogSearchFilters(**values), conflict


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


__all__ = [
    "interpretation_with_reason",
    "merge_llm_router_suggestion",
]
