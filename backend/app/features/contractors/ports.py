from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.domain.ids import ContractorEntityId
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.entities.resolution import RawContractorMapping
from app.features.ingest.entities.document import Document  # allowed cross-feature exception


class ContractorNotFound(Exception):
    def __init__(self, contractor_id: ContractorEntityId) -> None:
        super().__init__(f"Contractor not found: {contractor_id}")
        self.contractor_id = contractor_id


@runtime_checkable
class ContractorRepository(Protocol):
    async def add(self, contractor: Contractor) -> None: ...

    async def get(self, id: ContractorEntityId) -> Contractor: ...

    async def find_by_inn(self, inn: str) -> Contractor | None: ...

    async def find_by_normalized_key(self, key: str) -> Contractor | None: ...

    async def find_all_for_fuzzy(self) -> list[Contractor]: ...

    async def count_documents_for(self, id: ContractorEntityId) -> int: ...

    async def list_for_contractor(
        self,
        id: ContractorEntityId,
        *,
        limit: int,
        offset: int,
    ) -> list[Document]: ...


@runtime_checkable
class RawContractorMappingRepository(Protocol):
    async def add(self, mapping: RawContractorMapping) -> None: ...

    async def find_by_raw(
        self,
        raw_name: str,
        inn: str | None,
    ) -> RawContractorMapping | None: ...

    async def count_for(self, contractor_id: ContractorEntityId) -> int: ...


__all__ = [
    "ContractorNotFound",
    "ContractorRepository",
    "RawContractorMappingRepository",
]
