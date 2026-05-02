from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.documents.use_cases.list_documents import ListDocumentsUseCase
from app.features.ingest.entities.document import Document, DocumentStatus


class FakeDocumentRepository:
    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents
        self.list_calls: list[dict[str, object]] = []

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        status: DocumentStatus | None = None,
        contractor_entity_id: ContractorEntityId | None = None,
    ) -> list[Document]:
        self.list_calls.append(
            {
                "limit": limit,
                "offset": offset,
                "status": status,
                "contractor_entity_id": contractor_entity_id,
            },
        )
        filtered = self.documents
        if status is not None:
            filtered = [document for document in filtered if document.status == status]
        if contractor_entity_id is not None:
            filtered = [
                document
                for document in filtered
                if document.contractor_entity_id == contractor_entity_id
            ]
        return filtered[offset : offset + limit]


async def test_list_documents_returns_dtos_with_defaults() -> None:
    first_contractor_id = ContractorEntityId(uuid4())
    second_contractor_id = ContractorEntityId(uuid4())
    documents = FakeDocumentRepository(
        [
            _document(0, first_contractor_id, DocumentStatus.INDEXED),
            _document(1, first_contractor_id, DocumentStatus.FAILED),
            _document(2, second_contractor_id, DocumentStatus.INDEXED),
        ],
    )

    result = await ListDocumentsUseCase(documents=documents).execute()

    assert [document.title for document in result] == [
        "contract_0.pdf",
        "contract_1.pdf",
        "contract_2.pdf",
    ]
    assert result[0].contractor_entity_id == first_contractor_id
    assert result[1].status == DocumentStatus.FAILED
    assert documents.list_calls == [
        {
            "limit": 50,
            "offset": 0,
            "status": None,
            "contractor_entity_id": None,
        },
    ]


async def test_list_documents_applies_filters_and_pagination() -> None:
    contractor_id = ContractorEntityId(uuid4())
    other_contractor_id = ContractorEntityId(uuid4())
    documents = FakeDocumentRepository(
        [
            _document(0, contractor_id, DocumentStatus.INDEXED),
            _document(1, contractor_id, DocumentStatus.INDEXED),
            _document(2, contractor_id, DocumentStatus.FAILED),
            _document(3, other_contractor_id, DocumentStatus.INDEXED),
        ],
    )

    result = await ListDocumentsUseCase(documents=documents).execute(
        limit=1,
        offset=1,
        status=DocumentStatus.INDEXED,
        contractor_id=contractor_id,
    )

    assert [document.title for document in result] == ["contract_1.pdf"]
    assert documents.list_calls == [
        {
            "limit": 1,
            "offset": 1,
            "status": DocumentStatus.INDEXED,
            "contractor_entity_id": contractor_id,
        },
    ]


def _document(
    index: int,
    contractor_id: ContractorEntityId,
    status: DocumentStatus,
) -> Document:
    return Document(
        id=DocumentId(uuid4()),
        contractor_entity_id=contractor_id,
        title=f"contract_{index}.pdf",
        file_path=f"/fake/uploads/contract_{index}.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type="contract",
        status=status,
        error_message="processing failed" if status == DocumentStatus.FAILED else None,
        partial_extraction=False,
        created_at=datetime(2026, 4, 29, 12, 0, tzinfo=UTC)
        + timedelta(minutes=index),
    )
