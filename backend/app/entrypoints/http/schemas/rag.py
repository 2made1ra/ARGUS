from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.search.dto import (
    ChatMessage,
    GlobalRagAnswer,
    RagAnswer,
    RagContractorResult,
    SourceRef,
)


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    def to_domain(self) -> ChatMessage:
        return ChatMessage(role=self.role, content=self.content)


class RagAnswerRequest(BaseModel):
    message: str
    history: list[ChatMessageIn] = Field(default_factory=list)
    limit: int = 10


class SourceRefOut(BaseModel):
    document_id: UUID
    contractor_id: UUID | None
    page_start: int | None
    page_end: int | None
    chunk_index: int
    score: float
    snippet: str
    document_title: str | None
    contractor_name: str | None

    @classmethod
    def from_domain(cls, source: SourceRef) -> "SourceRefOut":
        return cls(
            document_id=UUID(str(source.document_id)),
            contractor_id=UUID(str(source.contractor_id))
            if source.contractor_id is not None
            else None,
            page_start=source.page_start,
            page_end=source.page_end,
            chunk_index=source.chunk_index,
            score=source.score,
            snippet=source.snippet,
            document_title=source.document_title,
            contractor_name=source.contractor_name,
        )


class RagAnswerOut(BaseModel):
    answer: str
    sources: list[SourceRefOut]

    @classmethod
    def from_domain(cls, answer: RagAnswer) -> "RagAnswerOut":
        return cls(
            answer=answer.answer,
            sources=[SourceRefOut.from_domain(source) for source in answer.sources],
        )


class RagContractorOut(BaseModel):
    contractor_id: UUID
    name: str
    score: float
    matched_chunks_count: int
    document_count: int
    top_snippet: str

    @classmethod
    def from_domain(cls, result: RagContractorResult) -> "RagContractorOut":
        return cls(
            contractor_id=UUID(str(result.contractor_id)),
            name=result.name,
            score=result.score,
            matched_chunks_count=result.matched_chunks_count,
            document_count=result.document_count,
            top_snippet=result.top_snippet,
        )


class GlobalRagAnswerOut(BaseModel):
    answer: str
    contractors: list[RagContractorOut]
    sources: list[SourceRefOut]

    @classmethod
    def from_domain(cls, answer: GlobalRagAnswer) -> "GlobalRagAnswerOut":
        return cls(
            answer=answer.answer,
            contractors=[
                RagContractorOut.from_domain(contractor)
                for contractor in answer.contractors
            ],
            sources=[SourceRefOut.from_domain(source) for source in answer.sources],
        )


__all__ = [
    "ChatMessageIn",
    "GlobalRagAnswerOut",
    "RagAnswerOut",
    "RagAnswerRequest",
    "RagContractorOut",
    "SourceRefOut",
]
