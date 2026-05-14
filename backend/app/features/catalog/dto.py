from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

MatchReasonCode = Literal[
    "semantic",
    "keyword_name",
    "keyword_supplier",
    "keyword_inn",
    "keyword_source_text",
    "keyword_external_id",
]


@dataclass(frozen=True, slots=True)
class SearchPriceItemsFilters:
    supplier_city: str | None = None
    supplier_city_normalized: str | None = None
    category: str | None = None
    section: str | None = None
    supplier_status: str | None = None
    supplier_status_normalized: str | None = None
    has_vat: str | None = None
    vat_mode: str | None = None
    unit_price: Decimal | None = None
    unit_price_min: Decimal | None = None
    unit_price_max: Decimal | None = None


@dataclass(frozen=True, slots=True)
class MatchReason:
    code: MatchReasonCode
    label: str


@dataclass(frozen=True, slots=True)
class FoundPriceItem:
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
class SearchPriceItemsResult:
    items: list[FoundPriceItem]


__all__ = [
    "FoundPriceItem",
    "MatchReason",
    "MatchReasonCode",
    "SearchPriceItemsFilters",
    "SearchPriceItemsResult",
]
