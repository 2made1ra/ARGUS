from __future__ import annotations

import json
from dataclasses import fields
from typing import Any
from uuid import UUID

from app.features.assistant.domain.llm_router.contract import (
    ALLOWED_INTENTS,
    ALLOWED_INTERFACE_MODES,
    ALLOWED_REASON_CODES,
    ALLOWED_TOOL_INTENTS,
    BRIEF_LIST_FIELDS,
    BRIEF_SCALAR_FIELDS,
    FILTER_FIELDS,
)
from app.features.assistant.dto import (
    BriefState,
    CatalogSearchFilters,
    ChatTurn,
    Interpretation,
    LLMRouterMessage,
    LLMStructuredRouterRequest,
    SearchRequest,
    ServiceNeed,
    VisibleCandidate,
)


def build_llm_router_prompt(
    *,
    message: str,
    brief: BriefState,
    recent_turns: list[ChatTurn],
    visible_candidates: list[VisibleCandidate],
    deterministic: Interpretation,
) -> LLMStructuredRouterRequest:
    prompt_input = {
        "message": message,
        "active_brief": _brief_to_payload(brief),
        "recent_turns": [
            {"role": turn.role, "content": turn.content}
            for turn in recent_turns[-6:]
        ],
        "visible_candidates": [
            {
                "ordinal": candidate.ordinal,
                "item_id": str(candidate.item_id),
                "service_category": candidate.service_category,
            }
            for candidate in visible_candidates
        ],
        "deterministic_signals": _interpretation_to_payload(deterministic),
        "allowed_interface_modes": sorted(ALLOWED_INTERFACE_MODES),
        "allowed_intents": sorted(ALLOWED_INTENTS),
        "allowed_tool_intents": sorted(ALLOWED_TOOL_INTENTS),
        "strict_json_schema": llm_router_json_schema(),
    }
    return LLMStructuredRouterRequest(
        messages=[
            LLMRouterMessage(
                role="system",
                content=(
                    "You are ARGUS structured router. Return only one JSON object. "
                    "Do not invent catalog suppliers, prices, cities, INNs, contacts, "
                    "legal statuses, availability, SQL, HTTP calls or tool calls. "
                    "You may suggest structured interpretation only."
                ),
            ),
            LLMRouterMessage(
                role="user",
                content=json.dumps(
                    prompt_input,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        ],
    )


def _brief_to_payload(brief: BriefState) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in fields(BriefState):
        value = getattr(brief, field.name)
        payload[field.name] = _serialize_value(value)
    return payload


def _interpretation_to_payload(interpretation: Interpretation) -> dict[str, Any]:
    return {
        "interface_mode": interpretation.interface_mode.value,
        "intent": interpretation.intent,
        "confidence": interpretation.confidence,
        "reason_codes": list(interpretation.reason_codes),
        "brief_update": _brief_to_payload(interpretation.brief_update),
        "requested_actions": list(interpretation.requested_actions),
        "search_requests": [
            _search_request_to_payload(request)
            for request in interpretation.search_requests
        ],
        "verification_targets": [
            str(item_id) for item_id in interpretation.verification_targets
        ],
        "missing_fields": list(interpretation.missing_fields),
        "clarification_questions": list(interpretation.clarification_questions),
    }


def _search_request_to_payload(request: SearchRequest) -> dict[str, Any]:
    return {
        "query": request.query,
        "service_category": request.service_category,
        "filters": _filters_to_payload(request.filters),
        "priority": request.priority,
        "limit": request.limit,
    }


def _filters_to_payload(filters: CatalogSearchFilters) -> dict[str, Any]:
    return {
        field.name: getattr(filters, field.name)
        for field in fields(CatalogSearchFilters)
    }


def _serialize_value(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, ServiceNeed):
        return {
            "category": value.category,
            "priority": value.priority,
            "source": value.source,
            "reason": value.reason,
            "notes": value.notes,
        }
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def llm_router_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["interface_mode", "intent", "confidence"],
        "additionalProperties": False,
        "properties": {
            "interface_mode": {"enum": sorted(ALLOWED_INTERFACE_MODES)},
            "intent": {"enum": sorted(ALLOWED_INTENTS)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason_codes": {
                "type": "array",
                "items": {"enum": sorted(ALLOWED_REASON_CODES)},
            },
            "brief_update": _brief_update_schema(),
            "search_requests": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "query": {"type": "string"},
                        "service_category": {"type": ["string", "null"]},
                        "filters": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": _filter_schema_properties(),
                        },
                        "priority": {"type": "integer"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
            "tool_intents": {
                "type": "array",
                "items": {"enum": sorted(ALLOWED_TOOL_INTENTS)},
            },
            "missing_fields": {"type": "array", "items": {"type": "string"}},
            "clarification_questions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "user_visible_summary": {"type": ["string", "null"]},
        },
    }


def _brief_update_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for field_name in sorted(BRIEF_SCALAR_FIELDS):
        if field_name in {"audience_size", "budget_total", "budget_per_guest"}:
            properties[field_name] = {"type": ["integer", "null"]}
        else:
            properties[field_name] = {"type": ["string", "null"]}

    for field_name in sorted(BRIEF_LIST_FIELDS):
        properties[field_name] = {
            "type": "array",
            "items": {"type": "string"},
        }

    properties["service_needs"] = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["category"],
            "additionalProperties": False,
            "properties": {
                "category": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["required", "must_have", "nice_to_have"],
                },
                "source": {
                    "type": "string",
                    "enum": ["explicit", "policy_inferred"],
                },
                "reason": {"type": ["string", "null"]},
                "notes": {"type": ["string", "null"]},
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }


def _filter_schema_properties() -> dict[str, Any]:
    schemas: dict[str, dict[str, Any]] = {
        "supplier_city_normalized": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
        "supplier_status_normalized": {"type": ["string", "null"]},
        "has_vat": {"type": ["string", "null"]},
        "vat_mode": {"type": ["string", "null"]},
        "unit_price_min": {"type": ["integer", "null"]},
        "unit_price_max": {"type": ["integer", "null"]},
    }
    return {
        field: schemas[field]
        for field in sorted(FILTER_FIELDS)
    }


__all__ = ["build_llm_router_prompt", "llm_router_json_schema"]
