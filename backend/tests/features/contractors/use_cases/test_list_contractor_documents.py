from __future__ import annotations

from collections.abc import MutableSequence
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.ids import ContractorEntityId, DocumentId, new_contractor_entity_id
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.use_cases.list_contractor_documents import (
    ListContractorDocumentsUseCase,
)
from app.features.ingest.entities.document import Document, DocumentStatus


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeContractorRepository:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.docs_by_contractor: dict[ContractorEntityId, list[Document]] = {}

    async def list_for_contractor(
        self,
        id: ContractorEntityId,
        *,
        limit: int,
        offset: int,
    ) -> list[Document]:
        self.calls.append("contractors.list_for_contractor")
        stored = self.docs_by_contractor.get(id, [])
        return stored[offset : offset + limit]

    async def add(self, contractor: Contractor) -> None:  # pragma: no cover
        raise NotImplementedError

    async def get(self, id: ContractorEntityId) -> Contractor:  # pragma: no cover
        raise NotImplementedError

    async def get_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, Contractor]:  # pragma: no cover
        raise NotImplementedError

    async def find_by_inn(self, inn: str) -> Contractor | None:  # pragma: no cover
        raise NotImplementedError

    async def find_by_normalized_key(self, key: str) -> Contractor | None:  # pragma: no cover
        raise NotImplementedError

    async def find_all_for_fuzzy(self) -> list[Contractor]:  # pragma: no cover
        raise NotImplementedError

    async def count_documents_for(self, id: ContractorEntityId) -> int:  # pragma: no cover
        raise NotImplementedError

    async def count_documents_for_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, int]:  # pragma: no cover
        raise NotImplementedError

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        q: str | None = None,
    ) -> list[Contractor]:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _document(index: int, contractor_id: ContractorEntityId) -> Document:
    return Document(
        id=DocumentId(uuid4()),
        contractor_entity_id=contractor_id,
        title=f"contract_{index}.pdf",
        file_path=f"/fake/uploads/contract_{index}.pdf",
        content_type="application/pdf",
        document_kind=None,
        doc_type=None,
        status=DocumentStatus.INDEXED,
        error_message=None,
        partial_extraction=False,
        created_at=datetime.now(UTC),
    )


def _use_case(*, contractors: FakeContractorRepository) -> ListContractorDocumentsUseCase:
    return ListContractorDocumentsUseCase(contractors=contractors)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_pagination_returns_correct_slice() -> None:
    calls: list[str] = []
    contractor_id = new_contractor_entity_id()
    docs = [_document(i, contractor_id) for i in range(5)]

    contractors = FakeContractorRepository(calls)
    contractors.docs_by_contractor[contractor_id] = docs

    result = await _use_case(contractors=contractors).execute(
        contractor_id=contractor_id,
        limit=2,
        offset=2,
    )

    assert result == docs[2:4]
    assert len(result) == 2
    assert "contractors.list_for_contractor" in calls


async def test_empty_for_unknown_contractor() -> None:
    calls: list[str] = []
    unknown_id = new_contractor_entity_id()

    contractors = FakeContractorRepository(calls)

    result = await _use_case(contractors=contractors).execute(
        contractor_id=unknown_id,
        limit=20,
        offset=0,
    )

    assert result == []
    assert "contractors.list_for_contractor" in calls
