from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.adapters.sqlalchemy.documents import _to_entity
from app.adapters.sqlalchemy.models import Document as DocumentRow
from app.core.domain.ids import DocumentId
from app.features.ingest.entities.document import DocumentStatus


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
