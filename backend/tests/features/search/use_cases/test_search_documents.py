from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.search.dto import SearchGroup, SearchHit
from app.features.search.use_cases.search_documents import SearchDocumentsUseCase


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.4, 0.5, 0.6]]


class FakeVectorSearch:
    def __init__(self, groups: list[SearchGroup]) -> None:
        self.groups = groups
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        *,
        query_vector: list[float],
        limit: int,
        filter: dict[str, Any] | None = None,
        group_by: str | None = None,
        group_size: int = 3,
    ) -> list[SearchGroup]:
        self.calls.append(
            {
                "query_vector": query_vector,
                "limit": limit,
                "filter": filter,
                "group_by": group_by,
                "group_size": group_size,
            },
        )
        return self.groups


class FakeDocumentRepository:
    def __init__(self, documents: dict[DocumentId, Document]) -> None:
        self.documents = documents
        self.get_calls: list[DocumentId] = []
        self.get_many_calls: list[list[DocumentId]] = []

    async def add(self, document: Document) -> None:
        raise NotImplementedError

    async def get(self, document_id: DocumentId) -> Document:
        self.get_calls.append(document_id)
        return self.documents[document_id]

    async def get_many(self, ids: list[DocumentId]) -> dict[DocumentId, Document]:
        self.get_many_calls.append(ids)
        return {
            document_id: self.documents[document_id]
            for document_id in ids
            if document_id in self.documents
        }

    async def list(self, *, limit: int, offset: int) -> list[Document]:
        raise NotImplementedError

    async def update_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
    ) -> None:
        raise NotImplementedError

    async def update_processing_result(
        self,
        document_id: DocumentId,
        *,
        document_kind: str,
        partial_extraction: bool,
    ) -> None:
        raise NotImplementedError

    async def set_error(self, document_id: DocumentId, message: str) -> None:
        raise NotImplementedError

    async def set_contractor_entity_id(
        self,
        document_id: DocumentId,
        contractor_entity_id: ContractorEntityId | None,
    ) -> None:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_search_documents_filters_by_contractor_and_groups_by_document() -> None:
    contractor_id = ContractorEntityId(uuid4())
    first_document_id = DocumentId(uuid4())
    second_document_id = DocumentId(uuid4())
    groups = [
        _group(
            first_document_id,
            [
                _hit(score=0.84, text="first chunk", page_start=2),
                _hit(score=0.91, text="second chunk", page_start=5),
            ],
        ),
        _group(
            second_document_id,
            [_hit(score=0.97, text="top chunk", page_start=None)],
        ),
    ]
    embeddings = FakeEmbeddingService()
    vectors = FakeVectorSearch(groups)
    documents = FakeDocumentRepository(
        {
            first_document_id: _document(
                first_document_id,
                contractor_id,
                "Договор охраны",
                datetime(2026, 4, 12, 9, 30, tzinfo=UTC),
            ),
            second_document_id: _document(
                second_document_id,
                contractor_id,
                "Акт выполненных работ",
                datetime(2026, 4, 13, 10, 15, tzinfo=UTC),
            ),
        },
    )
    use_case = SearchDocumentsUseCase(
        embeddings=embeddings,
        vectors=vectors,
        documents=documents,
    )

    results = await use_case.execute(
        contractor_entity_id=contractor_id,
        query="охрана объекта",
        limit=1,
    )

    assert embeddings.calls == [["охрана объекта"]]
    assert vectors.calls == [
        {
            "query_vector": [0.4, 0.5, 0.6],
            "limit": 100,
            "filter": {
                "must": [
                    {
                        "key": "contractor_entity_id",
                        "match": {"value": str(contractor_id)},
                    },
                ],
            },
            "group_by": "document_id",
            "group_size": 3,
        },
    ]
    assert documents.get_many_calls == [[first_document_id, second_document_id]]
    assert documents.get_calls == []
    assert len(results) == 1
    assert results[0].document_id == second_document_id
    assert results[0].title == "Акт выполненных работ"
    assert results[0].date == "2026-04-13"
    assert results[0].matched_chunks[0].page is None
    assert results[0].matched_chunks[0].snippet == "top chunk"
    assert results[0].matched_chunks[0].score == 0.97


@pytest.mark.asyncio
async def test_search_documents_builds_chunk_snippets_from_qdrant_payload() -> None:
    contractor_id = ContractorEntityId(uuid4())
    document_id = DocumentId(uuid4())
    embeddings = FakeEmbeddingService()
    vectors = FakeVectorSearch(
        [
            _group(
                document_id,
                [
                    _hit(score=0.77, text="A" * 300, page_start="4"),
                    _hit(score=0.69, text="another payload text", page_start=6),
                ],
            ),
        ],
    )
    documents = FakeDocumentRepository(
        {
            document_id: _document(
                document_id,
                contractor_id,
                "Контракт",
                datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
            ),
        },
    )
    use_case = SearchDocumentsUseCase(
        embeddings=embeddings,
        vectors=vectors,
        documents=documents,
    )

    results = await use_case.execute(
        contractor_entity_id=contractor_id,
        query="оплата",
    )

    assert len(vectors.calls) == 1
    assert documents.get_many_calls == [[document_id]]
    assert documents.get_calls == []
    assert results[0].date == "2026-01-02"
    chunks = [
        (chunk.page, chunk.snippet, chunk.score)
        for chunk in results[0].matched_chunks
    ]
    assert chunks == [
        (4, "A" * 300, 0.77),
        (6, "another payload text", 0.69),
    ]


@pytest.mark.asyncio
async def test_search_documents_skips_groups_without_document_metadata() -> None:
    contractor_id = ContractorEntityId(uuid4())
    existing_document_id = DocumentId(uuid4())
    missing_document_id = DocumentId(uuid4())
    embeddings = FakeEmbeddingService()
    vectors = FakeVectorSearch(
        [
            _group(
                missing_document_id,
                [_hit(score=0.98, text="missing", page_start=1)],
            ),
            _group(
                existing_document_id,
                [_hit(score=0.76, text="existing", page_start=2)],
            ),
        ],
    )
    documents = FakeDocumentRepository(
        {
            existing_document_id: _document(
                existing_document_id,
                contractor_id,
                "Существующий договор",
                datetime(2026, 2, 3, 4, 5, tzinfo=UTC),
            ),
        },
    )
    use_case = SearchDocumentsUseCase(
        embeddings=embeddings,
        vectors=vectors,
        documents=documents,
    )

    results = await use_case.execute(
        contractor_entity_id=contractor_id,
        query="оплата",
    )

    assert documents.get_many_calls == [[missing_document_id, existing_document_id]]
    assert documents.get_calls == []
    assert [(result.document_id, result.title) for result in results] == [
        (existing_document_id, "Существующий договор"),
    ]


def _group(document_id: DocumentId, hits: list[SearchHit]) -> SearchGroup:
    return SearchGroup(group_key=str(document_id), hits=hits)


def _hit(*, score: float, text: str, page_start: int | str | None) -> SearchHit:
    return SearchHit(
        id=UUID(str(uuid4())),
        score=score,
        payload={"text": text, "page_start": page_start},
    )


def _document(
    document_id: DocumentId,
    contractor_id: ContractorEntityId,
    title: str,
    created_at: datetime,
) -> Document:
    return Document(
        id=document_id,
        contractor_entity_id=contractor_id,
        title=title,
        file_path=f"/data/uploads/{document_id}.pdf",
        content_type="application/pdf",
        document_kind="contract",
        doc_type=None,
        status=DocumentStatus.INDEXED,
        error_message=None,
        partial_extraction=False,
        created_at=created_at,
    )
