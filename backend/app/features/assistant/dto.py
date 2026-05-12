from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

RouterIntent = Literal[
    "brief_discovery",
    "supplier_search",
    "mixed",
    "clarification",
    "selection",
    "comparison",
    "verification",
    "render_brief",
]

ToolIntent = Literal[
    "update_brief",
    "search_items",
    "get_item_details",
    "select_item",
    "compare_items",
    "verify_supplier_status",
    "render_event_brief",
]

SupplierVerificationStatus = Literal[
    "active",
    "inactive",
    "not_found",
    "not_verified",
    "error",
]

ServiceNeedPriority = Literal["required", "must_have", "nice_to_have"]
ServiceNeedSource = Literal["explicit", "policy_inferred"]

MatchReasonCode = Literal[
    "semantic",
    "keyword_name",
    "keyword_supplier",
    "keyword_inn",
    "keyword_source_text",
    "keyword_external_id",
]


class AssistantInterfaceMode(StrEnum):
    BRIEF_WORKSPACE = "brief_workspace"
    CHAT_SEARCH = "chat_search"


class EventBriefWorkflowState(StrEnum):
    INTAKE = "intake"
    CLARIFYING = "clarifying"
    SERVICE_PLANNING = "service_planning"
    SUPPLIER_SEARCHING = "supplier_searching"
    SUPPLIER_VERIFICATION = "supplier_verification"
    BRIEF_READY = "brief_ready"
    BRIEF_RENDERED = "brief_rendered"
    SEARCH_CLARIFYING = "search_clarifying"
    SEARCHING = "searching"
    SEARCH_RESULTS_SHOWN = "search_results_shown"


@dataclass(frozen=True, slots=True)
class ServiceNeed:
    category: str
    priority: ServiceNeedPriority = "required"
    source: ServiceNeedSource = "explicit"
    reason: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class BriefState:
    event_type: str | None = None
    event_goal: str | None = None
    concept: str | None = None
    format: str | None = None
    city: str | None = None
    date_or_period: str | None = None
    audience_size: int | None = None
    venue: str | None = None
    venue_status: str | None = None
    venue_constraints: list[str] = field(default_factory=list)
    duration_or_time_window: str | None = None
    event_level: str | None = None
    budget: str | int | None = None
    budget_total: int | None = None
    budget_per_guest: int | None = None
    budget_notes: str | None = None
    catering_format: str | None = None
    technical_requirements: list[str] = field(default_factory=list)
    service_needs: list[ServiceNeed] = field(default_factory=list)
    required_services: list[str] = field(default_factory=list)
    must_have_services: list[str] = field(default_factory=list)
    nice_to_have_services: list[str] = field(default_factory=list)
    selected_item_ids: list[UUID] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.budget, int) and self.budget_total is None:
            object.__setattr__(self, "budget_total", self.budget)
        if isinstance(self.budget, str) and self.budget_notes is None:
            object.__setattr__(self, "budget_notes", self.budget)


@dataclass(frozen=True, slots=True)
class CatalogSearchFilters:
    supplier_city_normalized: str | None = None
    category: str | None = None
    supplier_status_normalized: str | None = None
    has_vat: str | None = None
    vat_mode: str | None = None
    unit_price_min: int | None = None
    unit_price_max: int | None = None


@dataclass(frozen=True, slots=True)
class SearchRequest:
    query: str
    service_category: str | None = None
    filters: CatalogSearchFilters = field(default_factory=CatalogSearchFilters)
    priority: int = 1
    limit: int = 8


@dataclass(frozen=True, slots=True)
class VisibleCandidate:
    ordinal: int
    item_id: UUID
    service_category: str | None = None


@dataclass(frozen=True, slots=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class LLMRouterMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class LLMStructuredRouterRequest:
    messages: list[LLMRouterMessage]


@dataclass(frozen=True, slots=True)
class RouterDecision:
    intent: RouterIntent
    confidence: float
    known_facts: dict[str, Any]
    missing_fields: list[str]
    should_search_now: bool
    search_query: str | None
    brief_update: BriefState
    interface_mode: AssistantInterfaceMode = AssistantInterfaceMode.CHAT_SEARCH
    workflow_stage: EventBriefWorkflowState = EventBriefWorkflowState.SEARCH_CLARIFYING
    reason_codes: list[str] = field(default_factory=list)
    search_requests: list[SearchRequest] = field(default_factory=list)
    tool_intents: list[ToolIntent] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    user_visible_summary: str | None = None
    action_plan: ActionPlan | None = None


@dataclass(frozen=True, slots=True)
class Interpretation:
    interface_mode: AssistantInterfaceMode
    intent: RouterIntent
    confidence: float
    reason_codes: list[str]
    brief_update: BriefState
    service_needs: list[ServiceNeed] = field(default_factory=list)
    requested_actions: list[ToolIntent] = field(default_factory=list)
    search_requests: list[SearchRequest] = field(default_factory=list)
    verification_targets: list[UUID] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    user_visible_summary: str | None = None


@dataclass(frozen=True, slots=True)
class ActionPlan:
    interface_mode: AssistantInterfaceMode
    workflow_stage: EventBriefWorkflowState
    tool_intents: list[ToolIntent] = field(default_factory=list)
    search_requests: list[SearchRequest] = field(default_factory=list)
    verification_targets: list[UUID] = field(default_factory=list)
    item_detail_ids: list[UUID] = field(default_factory=list)
    render_requested: bool = False
    missing_fields: list[str] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    skipped_actions: list[str] = field(default_factory=list)

    @property
    def should_search_now(self) -> bool:
        return "search_items" in self.tool_intents


@dataclass(frozen=True, slots=True)
class MatchReason:
    code: MatchReasonCode
    label: str


@dataclass(frozen=True, slots=True)
class FoundCatalogItem:
    id: UUID
    score: float
    name: str
    category: str | None
    unit: str
    unit_price: Decimal
    supplier: str | None
    supplier_city: str | None
    source_text_snippet: str | None
    source_text_full_available: bool
    match_reason: MatchReason
    result_group: str | None = None
    matched_service_category: str | None = None
    matched_service_categories: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CatalogItemDetail:
    id: UUID
    name: str
    category: str | None
    unit: str
    unit_price: Decimal
    supplier: str | None
    supplier_inn: str | None
    supplier_city: str | None
    supplier_phone: str | None
    supplier_email: str | None
    supplier_status: str | None
    source_text: str | None


@dataclass(frozen=True, slots=True)
class SupplierVerificationResult:
    item_id: UUID | None
    supplier_name: str | None
    supplier_inn: str | None
    ogrn: str | None
    legal_name: str | None
    status: SupplierVerificationStatus
    source: str
    checked_at: datetime | None
    risk_flags: list[str] = field(default_factory=list)
    message: str | None = None


@dataclass(frozen=True, slots=True)
class RenderedBriefSection:
    title: str
    items: list[str]


@dataclass(frozen=True, slots=True)
class RenderedEventBrief:
    title: str
    sections: list[RenderedBriefSection]
    open_questions: list[str]
    evidence: dict[str, list[str]]


@dataclass(frozen=True, slots=True)
class ToolResults:
    brief: BriefState
    found_items: list[FoundCatalogItem] = field(default_factory=list)
    item_details: list[CatalogItemDetail] = field(default_factory=list)
    verification_results: list[SupplierVerificationResult] = field(
        default_factory=list,
    )
    rendered_brief: RenderedEventBrief | None = None
    skipped_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AssistantChatRequest:
    session_id: UUID | None
    message: str
    brief: BriefState | None = None
    recent_turns: list[ChatTurn] = field(default_factory=list)
    visible_candidates: list[VisibleCandidate] = field(default_factory=list)
    candidate_item_ids: list[UUID] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AssistantChatResponse:
    session_id: UUID
    message: str
    router: RouterDecision
    brief: BriefState
    found_items: list[FoundCatalogItem]
    ui_mode: AssistantInterfaceMode = AssistantInterfaceMode.CHAT_SEARCH
    action_plan: ActionPlan | None = None
    verification_results: list[SupplierVerificationResult] = field(
        default_factory=list,
    )
    rendered_brief: RenderedEventBrief | None = None


__all__ = [
    "ActionPlan",
    "AssistantChatRequest",
    "AssistantChatResponse",
    "AssistantInterfaceMode",
    "BriefState",
    "CatalogItemDetail",
    "CatalogSearchFilters",
    "ChatTurn",
    "EventBriefWorkflowState",
    "FoundCatalogItem",
    "Interpretation",
    "LLMRouterMessage",
    "LLMStructuredRouterRequest",
    "MatchReason",
    "MatchReasonCode",
    "RenderedBriefSection",
    "RenderedEventBrief",
    "RouterDecision",
    "RouterIntent",
    "SearchRequest",
    "ServiceNeed",
    "SupplierVerificationResult",
    "SupplierVerificationStatus",
    "ToolIntent",
    "ToolResults",
    "VisibleCandidate",
]
