from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from app.core.domain.ids import ContractorEntityId, DocumentId

ChatRole = Literal["system", "user", "assistant"]


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


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str


@dataclass(frozen=True)
class SourceRef:
    document_id: DocumentId
    contractor_id: ContractorEntityId | None
    page_start: int | None
    page_end: int | None
    chunk_index: int
    score: float
    snippet: str
    document_title: str | None = None
    contractor_name: str | None = None


@dataclass(frozen=True)
class RagContextChunk:
    source_index: int
    source: SourceRef
    text: str


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    sources: list[SourceRef]


@dataclass(frozen=True)
class RagContractorResult:
    contractor_id: ContractorEntityId
    name: str
    score: float
    matched_chunks_count: int
    document_count: int
    top_snippet: str


@dataclass(frozen=True)
class GlobalRagAnswer:
    answer: str
    contractors: list[RagContractorResult]
    sources: list[SourceRef]


__all__ = [
    "ChatMessage",
    "ChatRole",
    "ChunkSnippet",
    "ContractorSearchResult",
    "DocumentSearchResult",
    "GlobalRagAnswer",
    "RagAnswer",
    "RagContextChunk",
    "RagContractorResult",
    "SearchGroup",
    "SearchHit",
    "SourceRef",
    "WithinDocumentResult",
]
