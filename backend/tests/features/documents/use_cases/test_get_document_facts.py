from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sage import ContractFields

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.documents.use_cases.get_document_facts import (
    GetDocumentFactsUseCase,
)
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


class FakeFieldsRepository:
    def __init__(self, fields: dict[DocumentId, ContractFields]) -> None:
        self.fields = fields
        self.get_calls: list[DocumentId] = []

    async def get(self, document_id: DocumentId) -> ContractFields | None:
        self.get_calls.append(document_id)
        return self.fields.get(document_id)


class FakeSummaryRepository:
    def __init__(self, summaries: dict[DocumentId, tuple[str, list[str]]]) -> None:
        self.summaries = summaries
        self.get_calls: list[DocumentId] = []

    async def get(self, document_id: DocumentId) -> tuple[str, list[str]] | None:
        self.get_calls.append(document_id)
        return self.summaries.get(document_id)


async def test_get_document_facts_maps_fields_summary_and_partial_flag() -> None:
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository(
        {document_id: _document(document_id, partial_extraction=True)},
    )
    fields = FakeFieldsRepository(
        {
            document_id: ContractFields(
                document_number="A-12",
                supplier_name="ООО Вектор",
            ),
        },
    )
    summaries = FakeSummaryRepository(
        {document_id: ("Summary text", ["First point", "Second point"])},
    )

    result = await _use_case(
        documents=documents,
        fields=fields,
        summaries=summaries,
    ).execute(document_id)

    assert result.fields == {
        **ContractFields().model_dump(),
        "document_number": "A-12",
        "supplier_name": "ООО Вектор",
    }
    assert result.summary == "Summary text"
    assert result.key_points == ["First point", "Second point"]
    assert result.partial_extraction is True
    assert documents.get_calls == [document_id]
    assert fields.get_calls == [document_id]
    assert summaries.get_calls == [document_id]


async def test_get_document_facts_returns_null_values_without_facts() -> None:
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository(
        {document_id: _document(document_id, partial_extraction=False)},
    )
    fields = FakeFieldsRepository({})
    summaries = FakeSummaryRepository({})

    result = await _use_case(
        documents=documents,
        fields=fields,
        summaries=summaries,
    ).execute(document_id)

    assert result.fields == ContractFields().model_dump()
    assert result.summary is None
    assert result.key_points == []
    assert result.partial_extraction is False
    assert documents.get_calls == [document_id]


async def test_get_document_facts_does_not_read_facts_when_document_is_missing() -> None:
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository({})
    fields = FakeFieldsRepository({})
    summaries = FakeSummaryRepository({})

    with pytest.raises(DocumentNotFound):
        await _use_case(
            documents=documents,
            fields=fields,
            summaries=summaries,
        ).execute(document_id)

    assert documents.get_calls == [document_id]
    assert fields.get_calls == []
    assert summaries.get_calls == []


def _use_case(
    *,
    documents: FakeDocumentRepository,
    fields: FakeFieldsRepository,
    summaries: FakeSummaryRepository,
) -> GetDocumentFactsUseCase:
    return GetDocumentFactsUseCase(
        documents=documents,
        fields=fields,
        summaries=summaries,
    )


def _document(document_id: DocumentId, *, partial_extraction: bool) -> Document:
    return Document(
        id=document_id,
        contractor_entity_id=ContractorEntityId(uuid4()),
        title="contract.pdf",
        file_path="/fake/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type="contract",
        status=DocumentStatus.INDEXED,
        error_message=None,
        partial_extraction=partial_extraction,
        created_at=datetime(2026, 4, 29, 12, 0, tzinfo=UTC),
    )
