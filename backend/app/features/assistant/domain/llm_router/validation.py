from __future__ import annotations

import json

from app.features.assistant.domain.llm_router.contract import (
    ALLOWED_INTENTS,
    ALLOWED_INTERFACE_MODES,
    ALLOWED_REASON_CODES,
    ALLOWED_TOOL_INTENTS,
    BRIEF_LIST_FIELDS,
    BRIEF_SCALAR_FIELDS,
    FILTER_FIELDS,
    UNSAFE_TOP_LEVEL_KEYS,
    LLMRouterSuggestion,
)
from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    CatalogSearchFilters,
    RouterIntent,
    SearchRequest,
    ServiceNeed,
    ToolIntent,
)


def validate_llm_router_json(raw: str) -> LLMRouterSuggestion | None:
    payload = _loads_json_object(raw)
    if payload is None or _has_unsafe_top_level_key(payload):
        return None

    return LLMRouterSuggestion(
        interface_mode=_interface_mode(payload.get("interface_mode")),
        intent=_intent(payload.get("intent")),
        confidence=_confidence(payload.get("confidence")),
        reason_codes=_reason_codes(payload.get("reason_codes")),
        brief_update=_brief_update(payload.get("brief_update")),
        search_requests=_search_requests(payload.get("search_requests")),
        tool_intents=_tool_intents(payload.get("tool_intents")),
        missing_fields=_strings(payload.get("missing_fields")),
        clarification_questions=_strings(payload.get("clarification_questions")),
        user_visible_summary=_optional_string(payload.get("user_visible_summary")),
    )


def _loads_json_object(raw: str) -> dict[str, object] | None:
    value = raw.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _has_unsafe_top_level_key(payload: dict[str, object]) -> bool:
    return any(key in UNSAFE_TOP_LEVEL_KEYS for key in payload)


def _interface_mode(value: object) -> AssistantInterfaceMode | None:
    if not isinstance(value, str) or value not in ALLOWED_INTERFACE_MODES:
        return None
    return AssistantInterfaceMode(value)


def _intent(value: object) -> RouterIntent | None:
    if not isinstance(value, str) or value not in ALLOWED_INTENTS:
        return None
    return value


def _tool_intents(value: object) -> list[ToolIntent]:
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if isinstance(item, str) and item in ALLOWED_TOOL_INTENTS
    ]


def _confidence(value: object) -> float:
    if not isinstance(value, int | float):
        return 0.0
    return max(0.0, min(float(value), 1.0))


def _reason_codes(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return _dedupe(
        [
            item
            for item in value
            if isinstance(item, str) and item in ALLOWED_REASON_CODES
        ],
    )


def _brief_update(value: object) -> BriefState:
    if not isinstance(value, dict):
        return BriefState()

    brief_values: dict[str, object] = {}
    for field_name in BRIEF_SCALAR_FIELDS:
        field_value = value.get(field_name)
        if field_name in {"audience_size", "budget_total", "budget_per_guest"}:
            brief_values[field_name] = _optional_int(field_value)
        else:
            brief_values[field_name] = _optional_string(field_value)

    for field_name in BRIEF_LIST_FIELDS:
        brief_values[field_name] = _strings(value.get(field_name))

    brief_values["service_needs"] = _service_needs(value.get("service_needs"))
    return BriefState(**brief_values)


def _service_needs(value: object) -> list[ServiceNeed]:
    if not isinstance(value, list):
        return []
    needs: list[ServiceNeed] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        category = _optional_string(item.get("category"))
        if category is None:
            continue
        priority = item.get("priority")
        source = item.get("source")
        if priority not in {"required", "must_have", "nice_to_have"}:
            priority = "required"
        if source not in {"explicit", "policy_inferred"}:
            source = "explicit"
        needs.append(
            ServiceNeed(
                category=category,
                priority=priority,
                source=source,
                reason=_optional_string(item.get("reason")),
                notes=_optional_string(item.get("notes")),
            ),
        )
    return needs


def _search_requests(value: object) -> list[SearchRequest]:
    if not isinstance(value, list):
        return []
    requests: list[SearchRequest] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        query = _optional_string(item.get("query"))
        if query is None:
            continue
        requests.append(
            SearchRequest(
                query=query,
                service_category=_optional_string(item.get("service_category")),
                filters=_filters(item.get("filters")),
                priority=_bounded_int(item.get("priority"), default=1, high=10),
                limit=_bounded_int(item.get("limit"), default=8, high=20),
            ),
        )
    return requests


def _filters(value: object) -> CatalogSearchFilters:
    if not isinstance(value, dict):
        return CatalogSearchFilters()
    known = {key: value[key] for key in value if key in FILTER_FIELDS}
    return CatalogSearchFilters(
        supplier_city_normalized=_optional_string(
            known.get("supplier_city_normalized"),
        ),
        category=_optional_string(known.get("category")),
        supplier_status_normalized=_optional_string(
            known.get("supplier_status_normalized"),
        ),
        has_vat=_optional_string(known.get("has_vat")),
        vat_mode=_optional_string(known.get("vat_mode")),
        unit_price_min=_optional_int(known.get("unit_price_min")),
        unit_price_max=_optional_int(known.get("unit_price_max")),
    )


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        string_value = _optional_string(item)
        if string_value is not None:
            result.append(string_value)
    return _dedupe(result)


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _bounded_int(value: object, *, default: int, high: int) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        return default
    return max(1, min(parsed, high))


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


__all__ = ["validate_llm_router_json"]
