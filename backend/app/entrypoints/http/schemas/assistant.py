from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.assistant.dto import (
    AssistantChatRequest,
    AssistantChatResponse,
    BriefState,
    FoundCatalogItem,
    MatchReason,
    RouterDecision,
)


class BriefStateIn(BaseModel):
    event_type: str | None = None
    city: str | None = None
    date_or_period: str | None = None
    audience_size: int | None = None
    venue: str | None = None
    venue_status: str | None = None
    duration_or_time_window: str | None = None
    budget: str | None = None
    event_level: str | None = None
    required_services: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)

    def to_domain(self) -> BriefState:
        return BriefState(
            event_type=self.event_type,
            city=self.city,
            date_or_period=self.date_or_period,
            audience_size=self.audience_size,
            venue=self.venue,
            venue_status=self.venue_status,
            duration_or_time_window=self.duration_or_time_window,
            budget=self.budget,
            event_level=self.event_level,
            required_services=list(self.required_services),
            constraints=list(self.constraints),
            preferences=list(self.preferences),
        )


class AssistantChatRequestIn(BaseModel):
    session_id: UUID | None = None
    message: str
    brief: BriefStateIn | None = None

    def to_domain(self) -> AssistantChatRequest:
        return AssistantChatRequest(
            session_id=self.session_id,
            message=self.message,
            brief=self.brief.to_domain() if self.brief is not None else BriefState(),
        )


class BriefStateOut(BaseModel):
    event_type: str | None
    city: str | None
    date_or_period: str | None
    audience_size: int | None
    venue: str | None
    venue_status: str | None
    duration_or_time_window: str | None
    budget: str | None
    event_level: str | None
    required_services: list[str]
    constraints: list[str]
    preferences: list[str]

    @classmethod
    def from_domain(cls, brief: BriefState) -> BriefStateOut:
        return cls(
            event_type=brief.event_type,
            city=brief.city,
            date_or_period=brief.date_or_period,
            audience_size=brief.audience_size,
            venue=brief.venue,
            venue_status=brief.venue_status,
            duration_or_time_window=brief.duration_or_time_window,
            budget=brief.budget,
            event_level=brief.event_level,
            required_services=list(brief.required_services),
            constraints=list(brief.constraints),
            preferences=list(brief.preferences),
        )


class RouterDecisionOut(BaseModel):
    intent: Literal[
        "brief_discovery",
        "supplier_search",
        "mixed",
        "clarification",
    ]
    confidence: float
    known_facts: dict[str, Any]
    missing_fields: list[str]
    should_search_now: bool
    search_query: str | None
    brief_update: BriefStateOut

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

    @classmethod
    def from_domain(cls, item: FoundCatalogItem) -> FoundCatalogItemOut:
        return cls(
            id=item.id,
            score=item.score,
            name=item.name,
            category=item.category,
            unit=item.unit,
            unit_price=_decimal_string(item.unit_price),
            supplier=item.supplier,
            supplier_city=item.supplier_city,
            source_text_snippet=item.source_text_snippet,
            source_text_full_available=item.source_text_full_available,
            match_reason=MatchReasonOut.from_domain(item.match_reason),
        )


class AssistantChatResponseOut(BaseModel):
    session_id: UUID
    message: str
    router: RouterDecisionOut
    brief: BriefStateOut
    found_items: list[FoundCatalogItemOut]

    @classmethod
    def from_domain(cls, response: AssistantChatResponse) -> AssistantChatResponseOut:
        return cls(
            session_id=response.session_id,
            message=response.message,
            router=RouterDecisionOut.from_domain(response.router),
            brief=BriefStateOut.from_domain(response.brief),
            found_items=[
                FoundCatalogItemOut.from_domain(item)
                for item in response.found_items
            ],
        )


def _decimal_string(value: Decimal) -> str:
    return f"{value:.2f}"


__all__ = [
    "AssistantChatRequestIn",
    "AssistantChatResponseOut",
    "BriefStateIn",
    "BriefStateOut",
    "FoundCatalogItemOut",
    "MatchReasonOut",
    "RouterDecisionOut",
]
