from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.domain.ids import ContractorEntityId, DocumentId


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


@dataclass
class ChunkSnippet:
    page: int | None
    snippet: str
    score: float


@dataclass
class DocumentSearchResult:
    document_id: DocumentId
    title: str
    date: str | None
    matched_chunks: list[ChunkSnippet]


@dataclass
class WithinDocumentResult:
    chunk_index: int
    page_start: int | None
    page_end: int | None
    section_type: str | None
    snippet: str
    score: float


__all__ = [
    "ChunkSnippet",
    "ContractorSearchResult",
    "DocumentSearchResult",
    "SearchGroup",
    "SearchHit",
    "WithinDocumentResult",
]
