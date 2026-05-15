from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.entrypoints.http.schemas.formatting import decimal_string
from app.features.assistant.dto import (
    ActionPlan,
    AssistantChatRequest,
    AssistantChatResponse,
    BriefState,
    CatalogItemDetail,
    CatalogSearchFilters,
    ChatTurn,
    FoundCatalogItem,
    MatchReason,
    RenderedBriefSection,
    RenderedEventBrief,
    RouterDecision,
    SearchRequest,
    ServiceNeed,
    SupplierVerificationResult,
    VisibleCandidate,
)


class ServiceNeedIn(BaseModel):
    category: str
    priority: Literal["required", "must_have", "nice_to_have"] = "required"
    source: Literal["explicit", "policy_inferred"] = "explicit"
    reason: str | None = None
    notes: str | None = None

    def to_domain(self) -> ServiceNeed:
        return ServiceNeed(
            category=self.category,
            priority=self.priority,
            source=self.source,
            reason=self.reason,
            notes=self.notes,
        )


class ServiceNeedOut(BaseModel):
    category: str
    priority: Literal["required", "must_have", "nice_to_have"]
    source: Literal["explicit", "policy_inferred"]
    reason: str | None
    notes: str | None

    @classmethod
    def from_domain(cls, need: ServiceNeed) -> ServiceNeedOut:
        return cls(
            category=need.category,
            priority=need.priority,
            source=need.source,
            reason=need.reason,
            notes=need.notes,
        )


class BriefStateIn(BaseModel):
    event_type: str | None = None
    event_goal: str | None = None
    concept: str | None = None
    format: str | None = None
    city: str | None = None
    date_or_period: str | None = None
    audience_size: int | None = None
    venue: str | None = None
    venue_status: str | None = None
    venue_constraints: list[str] = Field(default_factory=list)
    duration_or_time_window: str | None = None
    event_level: str | None = None
    budget: str | int | None = None
    budget_total: int | None = None
    budget_per_guest: int | None = None
    budget_notes: str | None = None
    catering_format: str | None = None
    technical_requirements: list[str] = Field(default_factory=list)
    service_needs: list[ServiceNeedIn] = Field(default_factory=list)
    required_services: list[str] = Field(default_factory=list)
    must_have_services: list[str] = Field(default_factory=list)
    nice_to_have_services: list[str] = Field(default_factory=list)
    selected_item_ids: list[UUID] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    def to_domain(self) -> BriefState:
        return BriefState(
            event_type=self.event_type,
            event_goal=self.event_goal,
            concept=self.concept,
            format=self.format,
            city=self.city,
            date_or_period=self.date_or_period,
            audience_size=self.audience_size,
            venue=self.venue,
            venue_status=self.venue_status,
            venue_constraints=list(self.venue_constraints),
            duration_or_time_window=self.duration_or_time_window,
            budget=self.budget,
            event_level=self.event_level,
            budget_total=self.budget_total,
            budget_per_guest=self.budget_per_guest,
            budget_notes=self.budget_notes,
            catering_format=self.catering_format,
            technical_requirements=list(self.technical_requirements),
            service_needs=[need.to_domain() for need in self.service_needs],
            required_services=list(self.required_services),
            must_have_services=list(self.must_have_services),
            nice_to_have_services=list(self.nice_to_have_services),
            selected_item_ids=list(self.selected_item_ids),
            constraints=list(self.constraints),
            preferences=list(self.preferences),
            open_questions=list(self.open_questions),
        )


class ChatTurnIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    def to_domain(self) -> ChatTurn:
        return ChatTurn(role=self.role, content=self.content)


class VisibleCandidateIn(BaseModel):
    ordinal: int
    item_id: UUID
    service_category: str | None = None

    def to_domain(self) -> VisibleCandidate:
        return VisibleCandidate(
            ordinal=self.ordinal,
            item_id=self.item_id,
            service_category=self.service_category,
        )


class AssistantChatRequestIn(BaseModel):
    session_id: UUID | None = None
    message: str
    brief: BriefStateIn | None = None
    recent_turns: list[ChatTurnIn] = Field(default_factory=list)
    visible_candidates: list[VisibleCandidateIn] = Field(default_factory=list)
    candidate_item_ids: list[UUID] = Field(default_factory=list)

    def to_domain(self) -> AssistantChatRequest:
        return AssistantChatRequest(
            session_id=self.session_id,
            message=self.message,
            brief=self.brief.to_domain() if self.brief is not None else BriefState(),
            recent_turns=[turn.to_domain() for turn in self.recent_turns],
            visible_candidates=[
                candidate.to_domain() for candidate in self.visible_candidates
            ],
            candidate_item_ids=list(self.candidate_item_ids),
        )


class BriefStateOut(BaseModel):
    event_type: str | None
    event_goal: str | None
    concept: str | None
    format: str | None
    city: str | None
    date_or_period: str | None
    audience_size: int | None
    venue: str | None
    venue_status: str | None
    venue_constraints: list[str]
    duration_or_time_window: str | None
    event_level: str | None
    budget: str | int | None
    budget_total: int | None
    budget_per_guest: int | None
    budget_notes: str | None
    catering_format: str | None
    technical_requirements: list[str]
    service_needs: list[ServiceNeedOut]
    required_services: list[str]
    must_have_services: list[str]
    nice_to_have_services: list[str]
    selected_item_ids: list[UUID]
    constraints: list[str]
    preferences: list[str]
    open_questions: list[str]

    @classmethod
    def from_domain(cls, brief: BriefState) -> BriefStateOut:
        return cls(
            event_type=brief.event_type,
            event_goal=brief.event_goal,
            concept=brief.concept,
            format=brief.format,
            city=brief.city,
            date_or_period=brief.date_or_period,
            audience_size=brief.audience_size,
            venue=brief.venue,
            venue_status=brief.venue_status,
            venue_constraints=list(brief.venue_constraints),
            duration_or_time_window=brief.duration_or_time_window,
            budget=brief.budget,
            event_level=brief.event_level,
            budget_total=brief.budget_total,
            budget_per_guest=brief.budget_per_guest,
            budget_notes=brief.budget_notes,
            catering_format=brief.catering_format,
            technical_requirements=list(brief.technical_requirements),
            service_needs=[
                ServiceNeedOut.from_domain(need) for need in brief.service_needs
            ],
            required_services=list(brief.required_services),
            must_have_services=list(brief.must_have_services),
            nice_to_have_services=list(brief.nice_to_have_services),
            selected_item_ids=list(brief.selected_item_ids),
            constraints=list(brief.constraints),
            preferences=list(brief.preferences),
            open_questions=list(brief.open_questions),
        )


class CatalogSearchFiltersOut(BaseModel):
    supplier_city_normalized: str | None
    category: str | None
    service_category: str | None
    supplier_status_normalized: str | None
    has_vat: str | None
    vat_mode: str | None
    unit_price_min: int | None
    unit_price_max: int | None

    @classmethod
    def from_domain(cls, filters: CatalogSearchFilters) -> CatalogSearchFiltersOut:
        return cls(
            supplier_city_normalized=filters.supplier_city_normalized,
            category=filters.category,
            service_category=filters.service_category,
            supplier_status_normalized=filters.supplier_status_normalized,
            has_vat=filters.has_vat,
            vat_mode=filters.vat_mode,
            unit_price_min=filters.unit_price_min,
            unit_price_max=filters.unit_price_max,
        )


class SearchRequestOut(BaseModel):
    query: str
    service_category: str | None
    filters: CatalogSearchFiltersOut
    priority: int
    limit: int

    @classmethod
    def from_domain(cls, request: SearchRequest) -> SearchRequestOut:
        return cls(
            query=request.query,
            service_category=request.service_category,
            filters=CatalogSearchFiltersOut.from_domain(request.filters),
            priority=request.priority,
            limit=request.limit,
        )


class RouterDecisionOut(BaseModel):
    intent: Literal[
        "brief_discovery",
        "supplier_search",
        "mixed",
        "clarification",
        "selection",
        "comparison",
        "verification",
        "render_brief",
    ]
    confidence: float
    known_facts: dict[str, Any]
    missing_fields: list[str]
    should_search_now: bool
    search_query: str | None
    brief_update: BriefStateOut
    interface_mode: Literal["brief_workspace", "chat_search"]
    workflow_stage: Literal[
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
    ]
    reason_codes: list[str]
    search_requests: list[SearchRequestOut]
    tool_intents: list[str]
    clarification_questions: list[str]
    user_visible_summary: str | None

    @classmethod
    def from_domain(cls, decision: RouterDecision) -> RouterDecisionOut:
        return cls(
            intent=decision.intent,
            confidence=decision.confidence,
            known_facts=dict(decision.known_facts),
            missing_fields=list(decision.missing_fields),
            should_search_now=decision.should_search_now,
            search_query=decision.search_query,
            brief_update=BriefStateOut.from_domain(decision.brief_update),
            interface_mode=decision.interface_mode.value,
            workflow_stage=decision.workflow_stage.value,
            reason_codes=list(decision.reason_codes),
            search_requests=[
                SearchRequestOut.from_domain(request)
                for request in decision.search_requests
            ],
            tool_intents=list(decision.tool_intents),
            clarification_questions=list(decision.clarification_questions),
            user_visible_summary=decision.user_visible_summary,
        )


class ActionPlanOut(BaseModel):
    interface_mode: Literal["brief_workspace", "chat_search"]
    workflow_stage: Literal[
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
    ]
    tool_intents: list[str]
    search_requests: list[SearchRequestOut]
    verification_targets: list[UUID]
    comparison_targets: list[UUID]
    item_detail_ids: list[UUID]
    render_requested: bool
    missing_fields: list[str]
    clarification_questions: list[str]
    skipped_actions: list[str]

    @classmethod
    def from_domain(cls, action_plan: ActionPlan) -> ActionPlanOut:
        return cls(
            interface_mode=action_plan.interface_mode.value,
            workflow_stage=action_plan.workflow_stage.value,
            tool_intents=list(action_plan.tool_intents),
            search_requests=[
                SearchRequestOut.from_domain(request)
                for request in action_plan.search_requests
            ],
            verification_targets=list(action_plan.verification_targets),
            comparison_targets=list(action_plan.comparison_targets),
            item_detail_ids=list(action_plan.item_detail_ids),
            render_requested=action_plan.render_requested,
            missing_fields=list(action_plan.missing_fields),
            clarification_questions=list(action_plan.clarification_questions),
            skipped_actions=list(action_plan.skipped_actions),
        )


class MatchReasonOut(BaseModel):
    code: Literal[
        "semantic",
        "keyword_name",
        "keyword_supplier",
        "keyword_inn",
        "keyword_source_text",
        "keyword_external_id",
    ]
    label: str

    @classmethod
    def from_domain(cls, reason: MatchReason) -> MatchReasonOut:
        return cls(code=reason.code, label=reason.label)


class FoundCatalogItemOut(BaseModel):
    id: UUID
    score: float
    name: str
    category: str | None
    unit: str
    unit_price: str
    supplier: str | None
    supplier_city: str | None
    source_text_snippet: str | None
    source_text_full_available: bool
    match_reason: MatchReasonOut
    result_group: str | None
    matched_service_category: str | None
    matched_service_categories: list[str]

    @classmethod
    def from_domain(cls, item: FoundCatalogItem) -> FoundCatalogItemOut:
        return cls(
            id=item.id,
            score=item.score,
            name=item.name,
            category=item.category,
            unit=item.unit,
            unit_price=decimal_string(item.unit_price),
            supplier=item.supplier,
            supplier_city=item.supplier_city,
            source_text_snippet=item.source_text_snippet,
            source_text_full_available=item.source_text_full_available,
            match_reason=MatchReasonOut.from_domain(item.match_reason),
            result_group=item.result_group,
            matched_service_category=item.matched_service_category,
            matched_service_categories=list(item.matched_service_categories),
        )


class CatalogItemDetailOut(BaseModel):
    id: UUID
    name: str
    category: str | None
    unit: str
    unit_price: str
    supplier: str | None
    supplier_inn: str | None
    supplier_city: str | None
    supplier_phone: str | None
    supplier_email: str | None
    supplier_status: str | None
    source_text: str | None

    @classmethod
    def from_domain(cls, detail: CatalogItemDetail) -> CatalogItemDetailOut:
        return cls(
            id=detail.id,
            name=detail.name,
            category=detail.category,
            unit=detail.unit,
            unit_price=decimal_string(detail.unit_price),
            supplier=detail.supplier,
            supplier_inn=detail.supplier_inn,
            supplier_city=detail.supplier_city,
            supplier_phone=detail.supplier_phone,
            supplier_email=detail.supplier_email,
            supplier_status=detail.supplier_status,
            source_text=detail.source_text,
        )


class SupplierVerificationResultOut(BaseModel):
    item_id: UUID | None
    supplier_name: str | None
    supplier_inn: str | None
    ogrn: str | None
    legal_name: str | None
    status: Literal["active", "inactive", "not_found", "not_verified", "error"]
    source: str
    checked_at: datetime | None
    risk_flags: list[str]
    message: str | None

    @classmethod
    def from_domain(
        cls,
        result: SupplierVerificationResult,
    ) -> SupplierVerificationResultOut:
        return cls(
            item_id=result.item_id,
            supplier_name=result.supplier_name,
            supplier_inn=result.supplier_inn,
            ogrn=result.ogrn,
            legal_name=result.legal_name,
            status=result.status,
            source=result.source,
            checked_at=result.checked_at,
            risk_flags=list(result.risk_flags),
            message=result.message,
        )


class RenderedBriefSectionOut(BaseModel):
    title: str
    items: list[str]

    @classmethod
    def from_domain(
        cls,
        section: RenderedBriefSection,
    ) -> RenderedBriefSectionOut:
        return cls(title=section.title, items=list(section.items))


class RenderedEventBriefOut(BaseModel):
    title: str
    sections: list[RenderedBriefSectionOut]
    open_questions: list[str]
    evidence: dict[str, list[str]]

    @classmethod
    def from_domain(cls, brief: RenderedEventBrief) -> RenderedEventBriefOut:
        return cls(
            title=brief.title,
            sections=[
                RenderedBriefSectionOut.from_domain(section)
                for section in brief.sections
            ],
            open_questions=list(brief.open_questions),
            evidence={key: list(value) for key, value in brief.evidence.items()},
        )


class AssistantChatResponseOut(BaseModel):
    session_id: UUID
    message: str
    ui_mode: Literal["brief_workspace", "chat_search"]
    router: RouterDecisionOut
    action_plan: ActionPlanOut | None
    brief: BriefStateOut
    found_items: list[FoundCatalogItemOut]
    item_details: list[CatalogItemDetailOut]
    verification_results: list[SupplierVerificationResultOut]
    rendered_brief: RenderedEventBriefOut | None

    @classmethod
    def from_domain(cls, response: AssistantChatResponse) -> AssistantChatResponseOut:
        return cls(
            session_id=response.session_id,
            message=response.message,
            ui_mode=response.ui_mode.value,
            router=RouterDecisionOut.from_domain(response.router),
            action_plan=(
                ActionPlanOut.from_domain(response.action_plan)
                if response.action_plan is not None
                else None
            ),
            brief=BriefStateOut.from_domain(response.brief),
            found_items=[
                FoundCatalogItemOut.from_domain(item)
                for item in response.found_items
            ],
            item_details=[
                CatalogItemDetailOut.from_domain(detail)
                for detail in response.item_details
            ],
            verification_results=[
                SupplierVerificationResultOut.from_domain(result)
                for result in response.verification_results
            ],
            rendered_brief=(
                RenderedEventBriefOut.from_domain(response.rendered_brief)
                if response.rendered_brief is not None
                else None
            ),
        )


__all__ = [
    "AssistantChatRequestIn",
    "AssistantChatResponseOut",
    "ActionPlanOut",
    "CatalogItemDetailOut",
    "BriefStateIn",
    "BriefStateOut",
    "SearchRequestOut",
    "ServiceNeedOut",
    "FoundCatalogItemOut",
    "MatchReasonOut",
    "RouterDecisionOut",
]
