from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.domain.ids import DocumentId
from app.features.documents.use_cases.delete_document import DeleteDocumentUseCase
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.ingest.ports import DocumentNotFound


class FakeDocumentRepository:
    def __init__(self, documents: dict[DocumentId, Document]) -> None:
        self.documents = documents
        self.get_calls: list[DocumentId] = []
        self.delete_calls: list[DocumentId] = []

    async def get(self, document_id: DocumentId) -> Document:
        self.get_calls.append(document_id)
        try:
            return self.documents[document_id]
        except KeyError as exc:
            raise DocumentNotFound(document_id) from exc

    async def delete(self, document_id: DocumentId) -> None:
        self.delete_calls.append(document_id)
        try:
            del self.documents[document_id]
        except KeyError as exc:
            raise DocumentNotFound(document_id) from exc


class FakeVectorIndex:
    def __init__(self) -> None:
        self.delete_calls: list[DocumentId] = []

    async def delete_document(self, document_id: DocumentId) -> None:
        self.delete_calls.append(document_id)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


async def test_delete_document_removes_vectors_then_document_and_commits() -> None:
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository({document_id: _document(document_id)})
    vectors = FakeVectorIndex()
    uow = FakeUnitOfWork()

    await DeleteDocumentUseCase(
        documents=documents,
        vectors=vectors,
        uow=uow,
    ).execute(document_id)

    assert documents.get_calls == [document_id]
    assert vectors.delete_calls == [document_id]
    assert documents.delete_calls == [document_id]
    assert document_id not in documents.documents
    assert uow.commit_calls == 1


async def test_delete_document_propagates_not_found_without_side_effects() -> None:
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository({})
    vectors = FakeVectorIndex()
    uow = FakeUnitOfWork()

    with pytest.raises(DocumentNotFound) as exc_info:
        await DeleteDocumentUseCase(
            documents=documents,
            vectors=vectors,
            uow=uow,
        ).execute(document_id)

    assert exc_info.value.document_id == document_id
    assert documents.get_calls == [document_id]
    assert vectors.delete_calls == []
    assert documents.delete_calls == []
    assert uow.commit_calls == 0


def _document(document_id: DocumentId) -> Document:
    return Document(
        id=document_id,
        contractor_entity_id=None,
        title="contract.pdf",
        file_path="/fake/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type="contract",
        status=DocumentStatus.INDEXED,
        error_message=None,
        partial_extraction=False,
        created_at=datetime(2026, 4, 29, 12, 30, tzinfo=UTC),
    )
