from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.domain.ids import ContractorEntityId


@dataclass
class SearchHit:
    id: UUID
    score: float
    payload: dict[str, Any]


@dataclass
class SearchGroup:
    group_key: str
    hits: list[SearchHit]


@dataclass
class ContractorSearchResult:
    contractor_id: ContractorEntityId
    name: str
    score: float
    matched_chunks_count: int
    top_snippet: str


__all__ = [
    "ContractorSearchResult",
    "SearchGroup",
    "SearchHit",
]
