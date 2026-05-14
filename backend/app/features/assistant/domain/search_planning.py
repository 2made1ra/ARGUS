from __future__ import annotations

import re
from dataclasses import fields

from app.features.assistant.domain.slot_extraction import extract_event_brief_slots
from app.features.assistant.domain.taxonomy import canonical_city_for
from app.features.assistant.dto import (
    BriefState,
    CatalogSearchFilters,
    EventBriefWorkflowState,
    RouterDecision,
    SearchRequest,
)

_DEFAULT_LIMIT = 8
_MAX_PLANNED_SEARCHES = 3
_AUDIENCE_RE = re.compile(r"(?P<size>\d{1,5})\s*(?:человек|гостей|гостя|гость)", re.I)


class SearchPlanner:
    def __init__(self, *, max_searches_per_turn: int = _MAX_PLANNED_SEARCHES) -> None:
        self._max_searches_per_turn = max(0, max_searches_per_turn)

    def plan(
        self,
        *,
        decision: RouterDecision,
        brief_before: BriefState,
        brief_after: BriefState,
        workflow_stage: EventBriefWorkflowState,
    ) -> list[SearchRequest]:
        del workflow_stage
        requests = _requests_from_decision(decision, brief_after)
        if not requests:
            return []

        all_request_categories = [
            request.service_category
            for request in requests
            if request.service_category is not None
        ]
        ordered = sorted(
            enumerate(requests),
            key=lambda item: _request_sort_key(
                index=item[0],
                request=item[1],
                all_categories=all_request_categories,
            ),
        )
        limited = [
            request
            for _index, request in ordered[: self._max_searches_per_turn]
        ]
        all_categories = [
            request.service_category
            for request in limited
            if request.service_category is not None
        ]
        fallback_slots = extract_event_brief_slots(
            " ".join(request.query for request in limited),
        )

        planned: list[SearchRequest] = []
        for index, request in enumerate(limited, start=1):
            filters = _planned_filters(
                request=request,
                brief_before=brief_before,
                brief_after=brief_after,
                fallback_slots=fallback_slots,
            )
            planned.append(
                SearchRequest(
                    query=_planned_query(
                        request=request,
                        brief_before=brief_before,
                        brief_after=brief_after,
                        fallback_slots=fallback_slots,
                        all_categories=all_categories,
                    ),
                    service_category=request.service_category,
                    filters=filters,
                    priority=index,
                    limit=request.limit,
                ),
            )
        return planned


def _requests_from_decision(
    decision: RouterDecision,
    brief_after: BriefState,
) -> list[SearchRequest]:
    if decision.action_plan is not None and decision.action_plan.search_requests:
        return _expand_uncategorized_requests(
            list(decision.action_plan.search_requests),
            brief_after,
        )
    if decision.search_requests:
        return _expand_uncategorized_requests(
            list(decision.search_requests),
            brief_after,
        )
    if decision.search_query is not None:
        categories = _service_categories_from_brief(brief_after)
        if not categories:
            return [SearchRequest(query=decision.search_query, limit=_DEFAULT_LIMIT)]
        return [
            SearchRequest(
                query=decision.search_query,
                service_category=category,
                priority=index,
                limit=_DEFAULT_LIMIT,
            )
            for index, category in enumerate(categories, start=1)
        ]
    return []


def _expand_uncategorized_requests(
    requests: list[SearchRequest],
    brief_after: BriefState,
) -> list[SearchRequest]:
    categories = _service_categories_from_brief(brief_after)
    if not categories:
        return requests

    expanded: list[SearchRequest] = []
    for request in requests:
        if request.service_category is not None:
            expanded.append(request)
            continue
        expanded.extend(
            SearchRequest(
                query=request.query,
                service_category=category,
                filters=request.filters,
                priority=request.priority + index,
                limit=request.limit,
            )
            for index, category in enumerate(categories)
        )
    return expanded


def _service_categories_from_brief(brief: BriefState) -> list[str]:
    categories = [
        *[need.category for need in brief.service_needs if need.source == "explicit"],
        *brief.required_services,
        *brief.must_have_services,
    ]
    return _dedupe(categories)


def _planned_filters(
    *,
    request: SearchRequest,
    brief_before: BriefState,
    brief_after: BriefState,
    fallback_slots: BriefState,
) -> CatalogSearchFilters:
    existing = request.filters
    city = (
        existing.supplier_city_normalized
        or _normalized_city(brief_after.city)
        or _normalized_city(brief_before.city)
        or _normalized_city(fallback_slots.city)
        or _normalized_city(canonical_city_for(request.query.lower()) or None)
    )
    unit_price_max = existing.unit_price_max
    if unit_price_max is None and request.service_category == "кейтеринг":
        unit_price_max = (
            brief_after.budget_per_guest
            or brief_before.budget_per_guest
            or fallback_slots.budget_per_guest
        )

    values = {field.name: getattr(existing, field.name) for field in fields(existing)}
    values["supplier_city_normalized"] = city
    values["unit_price_max"] = unit_price_max
    return CatalogSearchFilters(**values)


def _planned_query(
    *,
    request: SearchRequest,
    brief_before: BriefState,
    brief_after: BriefState,
    fallback_slots: BriefState,
    all_categories: list[str],
) -> str:
    base_query = _base_query_for_request(request, all_categories)
    parts: list[str] = []
    _append_unique(parts, request.service_category)
    _append_unique(parts, base_query)
    _append_unique(parts, brief_after.event_type or brief_before.event_type)
    audience_size = (
        brief_after.audience_size
        or brief_before.audience_size
        or fallback_slots.audience_size
        or _audience_size(request.query)
    )
    if audience_size is not None:
        _append_unique(parts, f"{audience_size} человек")
    city = brief_after.city or brief_before.city or fallback_slots.city
    if city is None:
        city = canonical_city_for(request.query.lower())
    _append_unique(parts, city)
    for constraint in [*brief_after.venue_constraints, *brief_before.venue_constraints]:
        _append_unique(parts, constraint)
    budget_per_guest = (
        brief_after.budget_per_guest
        or brief_before.budget_per_guest
        or fallback_slots.budget_per_guest
    )
    if budget_per_guest is not None:
        _append_unique(parts, f"до {budget_per_guest} на гостя")
    _append_unique(parts, brief_after.concept or brief_before.concept)
    return " ".join(parts)


def _base_query_for_request(
    request: SearchRequest,
    all_categories: list[str],
) -> str | None:
    base_query = _strip_search_prefix(request.query)
    lowered = base_query.lower()
    matched_categories = [
        category
        for category in all_categories
        if category is not None and category.lower() in lowered
    ]
    if len(matched_categories) > 1:
        return None
    if request.service_category is not None:
        category = request.service_category.lower()
        if lowered == category:
            return None
        if lowered.startswith(category):
            remainder = base_query[len(request.service_category) :].strip(" ,.;:-")
            return remainder or None
    return base_query or None


def _request_sort_key(
    *,
    index: int,
    request: SearchRequest,
    all_categories: list[str],
) -> tuple[int, int, int]:
    if _query_mentions_multiple_categories(request.query, all_categories):
        position = _category_position(request.query, request.service_category)
        if position >= 0:
            return (0, position, index)
    return (1, request.priority, index)


def _query_mentions_multiple_categories(query: str, all_categories: list[str]) -> bool:
    lowered = query.lower()
    return sum(1 for category in all_categories if category.lower() in lowered) > 1


def _category_position(query: str, category: str | None) -> int:
    if category is None:
        return -1
    return query.lower().find(category.lower())


def _strip_search_prefix(message: str) -> str:
    normalized = " ".join(message.strip().split())
    lowered = normalized.lower()
    for prefix in (
        "найди ",
        "подбери ",
        "покажи ",
        "посмотри ",
        "мне нужно ",
        "нужно ",
        "нужен ",
        "нужна ",
        "нужны ",
    ):
        if lowered.startswith(prefix):
            return normalized[len(prefix) :].strip()
    return normalized


def _audience_size(value: str) -> int | None:
    match = _AUDIENCE_RE.search(value)
    if match is None:
        return None
    return int(match.group("size"))


def _normalized_city(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.lower().replace("ё", "е").split())
    normalized = re.sub(r"^(г\.?|город)\s+", "", normalized)
    return normalized or None


def _append_unique(parts: list[str], value: str | None) -> None:
    if value is None:
        return
    normalized = " ".join(value.split())
    if not normalized:
        return
    lowered = normalized.lower()
    existing = " ".join(parts).lower()
    if lowered in existing:
        return
    parts.append(normalized)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


__all__ = ["SearchPlanner"]
