from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    RouterIntent,
    SearchRequest,
    ToolIntent,
)

LLM_ROUTER_MIN_CONFIDENCE = 0.55

ALLOWED_INTERFACE_MODES = {mode.value for mode in AssistantInterfaceMode}
ALLOWED_INTENTS = set(get_args(RouterIntent))
ALLOWED_TOOL_INTENTS = set(get_args(ToolIntent))
ALLOWED_REASON_CODES = {
    "brief_update_detected",
    "service_need_detected",
    "service_bundle_detected",
    "search_action_detected",
    "verification_requested",
    "render_brief_requested",
    "contextual_reference_resolved",
    "context_missing_for_reference",
    "llm_router_used",
    "llm_router_fallback_used",
    "llm_conflict_resolved",
    "event_creation_intent_detected",
    "direct_catalog_search_detected",
    "brief_workspace_selected",
    "chat_search_selected",
}

UNSAFE_TOP_LEVEL_KEYS = {
    "api_calls",
    "browser_actions",
    "function_call",
    "http_request",
    "http_requests",
    "sql",
    "tool_calls",
}
BRIEF_SCALAR_FIELDS = {
    "event_type",
    "event_goal",
    "concept",
    "format",
    "city",
    "date_or_period",
    "audience_size",
    "venue",
    "venue_status",
    "duration_or_time_window",
    "event_level",
    "budget_total",
    "budget_per_guest",
    "budget_notes",
    "catering_format",
}
BRIEF_LIST_FIELDS = {
    "venue_constraints",
    "technical_requirements",
    "required_services",
    "must_have_services",
    "nice_to_have_services",
    "constraints",
    "preferences",
    "open_questions",
}
FILTER_FIELDS = {
    "supplier_city_normalized",
    "category",
    "supplier_status_normalized",
    "has_vat",
    "vat_mode",
    "unit_price_min",
    "unit_price_max",
}


@dataclass(frozen=True, slots=True)
class LLMRouterSuggestion:
    interface_mode: AssistantInterfaceMode | None
    intent: RouterIntent | None
    confidence: float
    reason_codes: list[str]
    brief_update: BriefState
    search_requests: list[SearchRequest]
    tool_intents: list[ToolIntent]
    missing_fields: list[str]
    clarification_questions: list[str]
    user_visible_summary: str | None


__all__ = [
    "ALLOWED_INTENTS",
    "ALLOWED_INTERFACE_MODES",
    "ALLOWED_REASON_CODES",
    "ALLOWED_TOOL_INTENTS",
    "BRIEF_LIST_FIELDS",
    "BRIEF_SCALAR_FIELDS",
    "FILTER_FIELDS",
    "LLM_ROUTER_MIN_CONFIDENCE",
    "LLMRouterSuggestion",
    "UNSAFE_TOP_LEVEL_KEYS",
]
