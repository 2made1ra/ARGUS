"""Smoke test — SSE status stream emits transitions and closes on terminal status."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.domain.ids import DocumentId
from app.entrypoints.http.streams import _status_stream
from app.features.ingest.entities.document import Document, DocumentStatus


def _make_doc(document_id: DocumentId, status: DocumentStatus) -> Document:
    return Document(
        id=document_id,
        contractor_entity_id=None,
        title="contract.pdf",
        file_path="/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type=None,
        status=status,
        error_message=None,
        partial_extraction=False,
        created_at=datetime(2026, 5, 2, tzinfo=UTC),
    )


async def test_stream_emits_three_events_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    doc_id = DocumentId(uuid4())
    statuses = [DocumentStatus.QUEUED, DocumentStatus.PROCESSING, DocumentStatus.INDEXED]
    call_idx = 0

    async def fake_repo(document_id: DocumentId) -> Document:
        nonlocal call_idx
        s = statuses[min(call_idx, len(statuses) - 1)]
        call_idx += 1
        return _make_doc(document_id, s)

    events: list[str] = []
    async for event in _status_stream(doc_id, fake_repo):
        events.append(event)

    assert len(events) == 3

    expected = ["QUEUED", "PROCESSING", "INDEXED"]
    for raw, expected_status in zip(events, expected):
        payload = json.loads(raw.removeprefix("data: ").strip())
        assert payload["status"] == expected_status
        assert payload["document_id"] == str(doc_id)
        assert "error_message" not in payload

    assert call_idx == 3


async def test_stream_includes_error_message_on_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    doc_id = DocumentId(uuid4())

    async def fake_repo(document_id: DocumentId) -> Document:
        doc = _make_doc(document_id, DocumentStatus.FAILED)
        doc.error_message = "OCR crashed"
        return doc

    events: list[str] = []
    async for event in _status_stream(doc_id, fake_repo):
        events.append(event)

    assert len(events) == 1
    payload = json.loads(events[0].removeprefix("data: ").strip())
    assert payload["status"] == "FAILED"
    assert payload["error_message"] == "OCR crashed"


async def test_stream_retries_on_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    doc_id = DocumentId(uuid4())
    call_idx = 0

    async def fake_repo(document_id: DocumentId) -> Document:
        nonlocal call_idx
        call_idx += 1
        if call_idx == 1:
            raise RuntimeError("DB blip")
        return _make_doc(document_id, DocumentStatus.INDEXED)

    events: list[str] = []
    async for event in _status_stream(doc_id, fake_repo):
        events.append(event)

    assert len(events) == 1
    payload = json.loads(events[0].removeprefix("data: ").strip())
    assert payload["status"] == "INDEXED"
    assert call_idx == 2
