"""Smoke tests — one happy-path test per documents handler."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.entrypoints.http.dependencies import (
    get_document_facts_uc,
    get_document_preview_uc,
    get_document_rag_answer_uc,
    get_get_document_uc,
    get_list_documents_uc,
    get_search_within_uc,
    get_upload_uc,
)
from app.features.documents.dto import DocumentDTO, DocumentFactsDTO, DocumentPreviewDTO
from app.features.ingest.entities.document import DocumentStatus
from app.features.search.dto import RagAnswer, WithinDocumentResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_dto(document_id: DocumentId | None = None) -> DocumentDTO:
    return DocumentDTO(
        id=document_id or DocumentId(uuid4()),
        title="contract.pdf",
        status=DocumentStatus.INDEXED,
        doc_type="contract",
        document_kind="text",
        contractor_entity_id=ContractorEntityId(uuid4()),
        content_type="application/pdf",
        partial_extraction=False,
        error_message=None,
        created_at=datetime(2026, 4, 29, 12, 0, tzinfo=UTC),
        preview_available=True,
    )


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------


async def test_upload_returns_202_with_document_id(app: FastAPI) -> None:
    doc_id = DocumentId(uuid4())
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = doc_id
    app.dependency_overrides[get_upload_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/documents/upload",
            files={"file": ("sample.pdf", b"PDF content", "application/pdf")},
            data={"content_type": "application/pdf"},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert UUID(body["document_id"]) == UUID(str(doc_id))


# ---------------------------------------------------------------------------
# GET /documents/
# ---------------------------------------------------------------------------


async def test_list_documents_returns_200(app: FastAPI) -> None:
    dto = _doc_dto()
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = [dto]
    app.dependency_overrides[get_list_documents_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/documents/")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert UUID(items[0]["id"]) == UUID(str(dto.id))


# ---------------------------------------------------------------------------
# GET /documents/{id}
# ---------------------------------------------------------------------------


async def test_get_document_returns_200(app: FastAPI) -> None:
    doc_id = DocumentId(uuid4())
    dto = _doc_dto(doc_id)
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = dto
    app.dependency_overrides[get_get_document_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/documents/{doc_id}")

    assert resp.status_code == 200
    assert UUID(resp.json()["id"]) == UUID(str(doc_id))


# ---------------------------------------------------------------------------
# GET /documents/{id}/facts
# ---------------------------------------------------------------------------


async def test_get_document_facts_returns_200(app: FastAPI) -> None:
    doc_id = DocumentId(uuid4())
    dto = DocumentFactsDTO(
        fields={"document_number": "A-1", "supplier_name": "ООО Вектор"},
        summary="Short summary",
        key_points=["Point one"],
        partial_extraction=False,
    )
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = dto
    app.dependency_overrides[get_document_facts_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/documents/{doc_id}/facts")

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "Short summary"
    assert body["key_points"] == ["Point one"]


# ---------------------------------------------------------------------------
# GET /documents/{id}/search
# ---------------------------------------------------------------------------


async def test_search_within_document_returns_200(app: FastAPI) -> None:
    doc_id = DocumentId(uuid4())
    hit = WithinDocumentResult(
        chunk_index=0,
        page_start=1,
        page_end=1,
        section_type="body",
        snippet="relevant text",
        score=0.92,
    )
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = [hit]
    app.dependency_overrides[get_search_within_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/documents/{doc_id}/search?q=relevant")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["snippet"] == "relevant text"
    assert items[0]["score"] == pytest.approx(0.92)


async def test_answer_document_returns_200(app: FastAPI) -> None:
    doc_id = DocumentId(uuid4())
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = RagAnswer(
        answer="Документ описывает поставку.",
        sources=[],
    )
    app.dependency_overrides[get_document_rag_answer_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/documents/{doc_id}/answer",
            json={"message": "дай summary"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"answer": "Документ описывает поставку.", "sources": []}


async def test_document_preview_returns_pdf(
    app: FastAPI,
    tmp_path: Path,
) -> None:
    doc_id = DocumentId(uuid4())
    preview_path = tmp_path / "preview.pdf"
    preview_path.write_bytes(b"%PDF-1.4\n")
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = DocumentPreviewDTO(
        path=preview_path,
        media_type="application/pdf",
    )
    app.dependency_overrides[get_document_preview_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/documents/{doc_id}/preview")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content == b"%PDF-1.4\n"
