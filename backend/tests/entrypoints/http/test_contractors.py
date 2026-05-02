"""Smoke tests — one happy-path test per contractors handler."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.entrypoints.http.dependencies import (
    get_contractor_profile_uc,
    get_list_contractor_documents_uc,
    get_search_documents_uc,
)
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.use_cases.get_contractor_profile import ContractorProfile
from app.features.documents.dto import DocumentDTO
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.search.dto import ChunkSnippet, DocumentSearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contractor(contractor_id: ContractorEntityId | None = None) -> Contractor:
    return Contractor(
        id=contractor_id or ContractorEntityId(uuid4()),
        display_name="ООО Вектор",
        normalized_key="ooo vektor",
        inn="7701234567",
        kpp="770101001",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _document(doc_id: DocumentId | None = None) -> Document:
    return Document(
        id=doc_id or DocumentId(uuid4()),
        contractor_entity_id=ContractorEntityId(uuid4()),
        title="contract.pdf",
        file_path="/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type="contract",
        status=DocumentStatus.INDEXED,
        error_message=None,
        partial_extraction=False,
        created_at=datetime(2026, 4, 29, 12, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# GET /contractors/{id}
# ---------------------------------------------------------------------------


async def test_get_contractor_returns_200(app: FastAPI) -> None:
    contractor_id = ContractorEntityId(uuid4())
    profile = ContractorProfile(
        contractor=_contractor(contractor_id),
        document_count=5,
        raw_mapping_count=2,
    )
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = profile
    app.dependency_overrides[get_contractor_profile_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/contractors/{contractor_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert UUID(body["contractor"]["id"]) == UUID(str(contractor_id))
    assert body["contractor"]["display_name"] == "ООО Вектор"
    assert body["document_count"] == 5


# ---------------------------------------------------------------------------
# GET /contractors/{id}/documents
# ---------------------------------------------------------------------------


async def test_list_contractor_documents_returns_200(app: FastAPI) -> None:
    contractor_id = ContractorEntityId(uuid4())
    doc = _document()
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = [doc]
    app.dependency_overrides[get_list_contractor_documents_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/contractors/{contractor_id}/documents")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert UUID(items[0]["id"]) == UUID(str(doc.id))


# ---------------------------------------------------------------------------
# GET /contractors/{id}/search
# ---------------------------------------------------------------------------


async def test_search_contractor_documents_returns_200(app: FastAPI) -> None:
    contractor_id = ContractorEntityId(uuid4())
    result = DocumentSearchResult(
        document_id=DocumentId(uuid4()),
        title="agreement.pdf",
        date="2026-01-15",
        matched_chunks=[ChunkSnippet(page=1, snippet="clause text", score=0.88)],
    )
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = [result]
    app.dependency_overrides[get_search_documents_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/contractors/{contractor_id}/search?q=clause")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["title"] == "agreement.pdf"
    assert items[0]["matched_chunks"][0]["snippet"] == "clause text"
