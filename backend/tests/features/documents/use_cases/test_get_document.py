from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.documents.use_cases.get_document import GetDocumentUseCase
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.ingest.ports import DocumentNotFound


class FakeDocumentRepository:
    def __init__(self, documents: dict[DocumentId, Document]) -> None:
        self.documents = documents
        self.get_calls: list[DocumentId] = []

    async def get(self, document_id: DocumentId) -> Document:
        self.get_calls.append(document_id)
        try:
            return self.documents[document_id]
        except KeyError as exc:
            raise DocumentNotFound(document_id) from exc


async def test_get_document_returns_dto() -> None:
    document_id = DocumentId(uuid4())
    contractor_id = ContractorEntityId(uuid4())
    created_at = datetime(2026, 4, 29, 12, 30, tzinfo=UTC)
    document = _document(
        document_id,
        contractor_entity_id=contractor_id,
        created_at=created_at,
    )
    documents = FakeDocumentRepository({document_id: document})

    result = await GetDocumentUseCase(documents=documents).execute(document_id)

    assert result.id == document_id
    assert result.title == "contract.pdf"
    assert result.status == DocumentStatus.INDEXED
    assert result.doc_type == "contract"
    assert result.document_kind == "text"
    assert result.contractor_entity_id == contractor_id
    assert result.content_type == "application/pdf"
    assert result.partial_extraction is False
    assert result.error_message is None
    assert result.created_at == created_at
    assert documents.get_calls == [document_id]


async def test_get_document_propagates_not_found() -> None:
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository({})

    with pytest.raises(DocumentNotFound) as exc_info:
        await GetDocumentUseCase(documents=documents).execute(document_id)

    assert exc_info.value.document_id == document_id
    assert documents.get_calls == [document_id]


def _document(
    document_id: DocumentId,
    *,
    contractor_entity_id: ContractorEntityId | None,
    created_at: datetime,
) -> Document:
    return Document(
        id=document_id,
        contractor_entity_id=contractor_entity_id,
        title="contract.pdf",
        file_path="/fake/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type="contract",
        status=DocumentStatus.INDEXED,
        error_message=None,
        partial_extraction=False,
        created_at=created_at,
    )
