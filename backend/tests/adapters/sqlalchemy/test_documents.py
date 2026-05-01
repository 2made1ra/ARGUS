from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.adapters.sqlalchemy.documents import (
    SqlAlchemyDocumentRepository,
    _to_entity,
)
from app.adapters.sqlalchemy.models import Document as DocumentRow
from app.core.domain.ids import DocumentId
from app.features.ingest.entities.document import DocumentStatus
from sqlalchemy.ext.asyncio import AsyncSession


def _document_row() -> DocumentRow:
    return DocumentRow(
        id=uuid4(),
        contractor_entity_id=None,
        title="contract.pdf",
        file_path="/fake/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type="contract",
        status="QUEUED",
        error_message=None,
        partial_extraction=False,
        created_at=datetime.now(UTC),
    )


def test_to_entity_maps_required_document_fields() -> None:
    row = _document_row()

    document = _to_entity(row)

    assert document.id == DocumentId(row.id)
    assert document.title == "contract.pdf"
    assert document.file_path == "/fake/uploads/contract.pdf"
    assert document.content_type == "application/pdf"
    assert document.status == DocumentStatus.QUEUED
    assert document.partial_extraction is False
    assert document.created_at == row.created_at


def test_to_entity_rejects_missing_required_document_field() -> None:
    row = _document_row()
    row.title = None

    with pytest.raises(ValueError, match="Document row is missing title"):
        _to_entity(row)


def test_to_entity_rejects_invalid_document_status() -> None:
    row = _document_row()
    row.status = "CORRUPTED"

    with pytest.raises(ValueError, match="Document row has invalid status: CORRUPTED"):
        _to_entity(row)


@pytest.mark.asyncio
async def test_get_many_loads_documents_with_one_query() -> None:
    first = _document_row()
    second = _document_row()
    missing_id = DocumentId(uuid4())
    session = AsyncMock()
    session.scalars.return_value = [first, second]
    repository = SqlAlchemyDocumentRepository(cast(AsyncSession, session))

    documents = await repository.get_many(
        [DocumentId(first.id), missing_id, DocumentId(second.id)],
    )

    session.scalars.assert_awaited_once()
    assert set(documents) == {DocumentId(first.id), DocumentId(second.id)}
    assert documents[DocumentId(first.id)].title == first.title
    assert documents[DocumentId(second.id)].title == second.title


@pytest.mark.asyncio
async def test_get_many_short_circuits_empty_ids() -> None:
    session = AsyncMock()
    repository = SqlAlchemyDocumentRepository(cast(AsyncSession, session))

    documents = await repository.get_many([])

    assert documents == {}
    session.scalars.assert_not_called()
