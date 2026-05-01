from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.domain.ids import DocumentId
from app.features.search.dto import SearchHit
from app.features.search.use_cases.search_within_document import (
    SearchWithinDocumentUseCase,
)


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.7, 0.8, 0.9]]


class FakeVectorSearch:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        *,
        query_vector: list[float],
        limit: int,
        filter: dict[str, Any] | None = None,
        group_by: str | None = None,
        group_size: int = 3,
    ) -> list[SearchHit]:
        self.calls.append(
            {
                "query_vector": query_vector,
                "limit": limit,
                "filter": filter,
                "group_by": group_by,
                "group_size": group_size,
            },
        )
        return self.hits


@pytest.mark.asyncio
async def test_search_within_document_filters_by_document_and_excludes_summary() -> None:
    document_id = DocumentId(uuid4())
    embeddings = FakeEmbeddingService()
    vectors = FakeVectorSearch(
        [
            _hit(
                score=0.92,
                chunk_index=3,
                text="A" * 300,
                page_start=4,
                page_end=5,
                section_type="payment",
            ),
            _hit(
                score=0.81,
                chunk_index=4,
                text="second chunk",
                page_start=None,
                page_end=None,
                section_type=None,
            ),
        ],
    )
    use_case = SearchWithinDocumentUseCase(embeddings=embeddings, vectors=vectors)

    results = await use_case.execute(
        document_id=document_id,
        query="условия оплаты",
        limit=7,
    )

    assert embeddings.calls == [["условия оплаты"]]
    assert vectors.calls == [
        {
            "query_vector": [0.7, 0.8, 0.9],
            "limit": 7,
            "filter": {
                "must": [
                    {
                        "key": "document_id",
                        "match": {"value": str(document_id)},
                    },
                ],
                "must_not": [
                    {
                        "key": "is_summary",
                        "match": {"value": True},
                    },
                ],
            },
            "group_by": None,
            "group_size": 3,
        },
    ]
    assert len(results) == 2
    assert results[0].chunk_index == 3
    assert results[0].page_start == 4
    assert results[0].page_end == 5
    assert results[0].section_type == "payment"
    assert results[0].snippet == "A" * 300
    assert results[0].score == 0.92
    assert results[1].chunk_index == 4
    assert results[1].page_start is None
    assert results[1].page_end is None
    assert results[1].section_type is None
    assert results[1].snippet == "second chunk"


@pytest.mark.asyncio
async def test_search_within_document_does_not_return_summary_payloads() -> None:
    embeddings = FakeEmbeddingService()
    vectors = FakeVectorSearch(
        [
            _hit(
                score=0.99,
                chunk_index=0,
                text="summary text",
                page_start=None,
                page_end=None,
                section_type="summary",
                is_summary=True,
            ),
            _hit(
                score=0.88,
                chunk_index="5",
                text="regular chunk",
                page_start="8",
                page_end="9",
                section_type="terms",
            ),
        ],
    )
    use_case = SearchWithinDocumentUseCase(embeddings=embeddings, vectors=vectors)

    results = await use_case.execute(document_id=DocumentId(uuid4()), query="срок")

    assert len(vectors.calls) == 1
    assert [(result.chunk_index, result.snippet) for result in results] == [
        (5, "regular chunk"),
    ]
    assert results[0].page_start == 8
    assert results[0].page_end == 9
    assert results[0].section_type == "terms"


def _hit(
    *,
    score: float,
    chunk_index: int | str,
    text: str,
    page_start: int | str | None,
    page_end: int | str | None,
    section_type: str | None,
    is_summary: bool = False,
) -> SearchHit:
    return SearchHit(
        id=UUID(str(uuid4())),
        score=score,
        payload={
            "chunk_index": chunk_index,
            "text": text,
            "page_start": page_start,
            "page_end": page_end,
            "section_type": section_type,
            "is_summary": is_summary,
        },
    )
