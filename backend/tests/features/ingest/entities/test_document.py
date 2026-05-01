from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from app.core.domain.ids import DocumentId
from app.features.ingest.entities.document import (
    Document,
    DocumentStatus,
    InvalidStatusTransition,
)


def make_document(status: DocumentStatus | str) -> Document:
    return Document(
        id=DocumentId(uuid4()),
        contractor_entity_id=None,
        title="contract.pdf",
        file_path="/tmp/contract.pdf",
        content_type="application/pdf",
        document_kind=None,
        doc_type=None,
        status=cast(DocumentStatus, status),
        error_message=None,
        partial_extraction=False,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("initial_status", "transition", "expected_status"),
    [
        (
            DocumentStatus.QUEUED,
            Document.mark_processing,
            DocumentStatus.PROCESSING,
        ),
        (
            DocumentStatus.PROCESSING,
            Document.mark_resolving,
            DocumentStatus.RESOLVING,
        ),
        (
            DocumentStatus.RESOLVING,
            Document.mark_indexing,
            DocumentStatus.INDEXING,
        ),
        (
            DocumentStatus.INDEXING,
            Document.mark_indexed,
            DocumentStatus.INDEXED,
        ),
    ],
)
def test_valid_status_transitions_pass(
    initial_status: DocumentStatus,
    transition: Callable[[Document], None],
    expected_status: DocumentStatus,
) -> None:
    document = make_document(initial_status)

    transition(document)

    assert document.status == expected_status


@pytest.mark.parametrize(
    ("transition", "target_status", "allowed_status"),
    [
        (Document.mark_processing, DocumentStatus.PROCESSING, DocumentStatus.QUEUED),
        (
            Document.mark_resolving,
            DocumentStatus.RESOLVING,
            DocumentStatus.PROCESSING,
        ),
        (Document.mark_indexing, DocumentStatus.INDEXING, DocumentStatus.RESOLVING),
        (Document.mark_indexed, DocumentStatus.INDEXED, DocumentStatus.INDEXING),
    ],
)
@pytest.mark.parametrize("initial_status", list(DocumentStatus))
def test_invalid_status_transitions_raise(
    transition: Callable[[Document], None],
    target_status: DocumentStatus,
    allowed_status: DocumentStatus,
    initial_status: DocumentStatus,
) -> None:
    if initial_status == allowed_status:
        return
    document = make_document(initial_status)

    with pytest.raises(InvalidStatusTransition) as exc_info:
        transition(document)

    assert exc_info.value.current_status == initial_status
    assert exc_info.value.target_status == target_status


@pytest.mark.parametrize(
    "initial_status",
    [
        DocumentStatus.QUEUED,
        DocumentStatus.PROCESSING,
        DocumentStatus.RESOLVING,
        DocumentStatus.INDEXING,
        DocumentStatus.FAILED,
    ],
)
def test_mark_failed_passes_from_any_non_indexed_status(
    initial_status: DocumentStatus,
) -> None:
    document = make_document(initial_status)

    document.mark_failed("SAGE processing failed")

    assert document.status == DocumentStatus.FAILED
    assert document.error_message == "SAGE processing failed"


def test_mark_failed_from_indexed_raises() -> None:
    document = make_document(DocumentStatus.INDEXED)

    with pytest.raises(InvalidStatusTransition) as exc_info:
        document.mark_failed("late failure")

    assert exc_info.value.current_status == DocumentStatus.INDEXED
    assert exc_info.value.target_status == DocumentStatus.FAILED
    assert document.error_message is None


def test_document_coerces_persisted_string_status() -> None:
    document = make_document("QUEUED")

    assert document.status == DocumentStatus.QUEUED
