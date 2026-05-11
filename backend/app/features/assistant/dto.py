from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

RouterIntent = Literal[
    "brief_discovery",
    "supplier_search",
    "mixed",
    "clarification",
]

MatchReasonCode = Literal[
    "semantic",
    "keyword_name",
    "keyword_supplier",
    "keyword_inn",
    "keyword_source_text",
    "keyword_external_id",
]


@dataclass(frozen=True, slots=True)
class BriefState:
    event_type: str | None = None
    city: str | None = None
    date_or_period: str | None = None
    audience_size: int | None = None
    venue: str | None = None
    venue_status: str | None = None
    duration_or_time_window: str | None = None
    budget: str | None = None
    event_level: str | None = None
    required_services: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RouterDecision:
    intent: RouterIntent
    confidence: float
    known_facts: dict[str, Any]
    missing_fields: list[str]
    should_search_now: bool
    search_query: str | None
    brief_update: BriefState


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


@dataclass(frozen=True, slots=True)
class AssistantChatRequest:
    session_id: UUID | None
    message: str
    brief: BriefState | None = None


@dataclass(frozen=True, slots=True)
class AssistantChatResponse:
    session_id: UUID
    message: str
    router: RouterDecision
    brief: BriefState
    found_items: list[FoundCatalogItem]


__all__ = [
    "AssistantChatRequest",
    "AssistantChatResponse",
    "BriefState",
    "FoundCatalogItem",
    "MatchReason",
    "MatchReasonCode",
    "RouterDecision",
    "RouterIntent",
]
