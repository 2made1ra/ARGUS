from __future__ import annotations

from collections.abc import MutableSequence
from datetime import UTC, datetime

from app.core.domain.ids import ContractorEntityId, new_contractor_entity_id
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.entities.resolution import RawContractorMapping
from app.features.contractors.ports import ContractorNotFound
from app.features.contractors.use_cases.get_contractor_profile import (
    ContractorProfile,
    GetContractorProfileUseCase,
)
from app.features.ingest.entities.document import Document

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeContractorRepository:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.store: dict[ContractorEntityId, Contractor] = {}
        self.doc_counts: dict[ContractorEntityId, int] = {}

    async def get(self, id: ContractorEntityId) -> Contractor:
        self.calls.append("contractors.get")
        if id not in self.store:
            raise ContractorNotFound(id)
        return self.store[id]

    async def get_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, Contractor]:  # pragma: no cover
        raise NotImplementedError

    async def count_documents_for(self, id: ContractorEntityId) -> int:
        self.calls.append("contractors.count_documents_for")
        return self.doc_counts.get(id, 0)

    async def count_documents_for_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, int]:  # pragma: no cover
        raise NotImplementedError

    async def add(self, contractor: Contractor) -> None:  # pragma: no cover
        raise NotImplementedError

    async def find_by_inn(self, inn: str) -> Contractor | None:  # pragma: no cover
        raise NotImplementedError

    async def find_by_normalized_key(
        self,
        key: str,
    ) -> Contractor | None:  # pragma: no cover
        raise NotImplementedError

    async def find_all_for_fuzzy(self) -> list[Contractor]:  # pragma: no cover
        raise NotImplementedError

    async def list_for_contractor(
        self, id: ContractorEntityId, *, limit: int, offset: int
    ) -> list[Document]:  # pragma: no cover
        raise NotImplementedError

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        q: str | None = None,
    ) -> list[Contractor]:  # pragma: no cover
        raise NotImplementedError


class FakeRawContractorMappingRepository:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.mapping_counts: dict[ContractorEntityId, int] = {}

    async def count_for(self, contractor_id: ContractorEntityId) -> int:
        self.calls.append("mappings.count_for")
        return self.mapping_counts.get(contractor_id, 0)

    async def add(self, mapping: RawContractorMapping) -> None:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contractor(contractor_id: ContractorEntityId) -> Contractor:
    return Contractor(
        id=contractor_id,
        display_name="Тест Контрактор",
        normalized_key="тест контрактор",
        inn="7701234567",
        kpp=None,
        created_at=datetime.now(UTC),
    )


def _use_case(
    *,
    contractors: FakeContractorRepository,
    mappings: FakeRawContractorMappingRepository,
) -> GetContractorProfileUseCase:
    return GetContractorProfileUseCase(contractors=contractors, mappings=mappings)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_returns_profile_with_counts() -> None:
    calls: list[str] = []
    contractor_id = new_contractor_entity_id()
    contractor = _contractor(contractor_id)

    contractors = FakeContractorRepository(calls)
    contractors.store[contractor_id] = contractor
    contractors.doc_counts[contractor_id] = 7

    mappings = FakeRawContractorMappingRepository(calls)
    mappings.mapping_counts[contractor_id] = 3

    profile = await _use_case(contractors=contractors, mappings=mappings).execute(
        contractor_id
    )

    assert isinstance(profile, ContractorProfile)
    assert profile.contractor == contractor
    assert profile.document_count == 7
    assert profile.raw_mapping_count == 3
    assert "contractors.get" in calls
    assert "contractors.count_documents_for" in calls
    assert "mappings.count_for" in calls


async def test_not_found_propagates() -> None:
    calls: list[str] = []
    unknown_id = new_contractor_entity_id()

    contractors = FakeContractorRepository(calls)
    mappings = FakeRawContractorMappingRepository(calls)

    try:
        await _use_case(contractors=contractors, mappings=mappings).execute(unknown_id)
        raise AssertionError("ContractorNotFound was not raised")
    except ContractorNotFound as exc:
        assert exc.contractor_id == unknown_id

    assert "contractors.get" in calls
    assert "contractors.count_documents_for" not in calls
    assert "mappings.count_for" not in calls
