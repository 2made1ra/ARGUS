from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.ids import ContractorEntityId
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.ports import ContractorRepository, RawContractorMappingRepository


@dataclass
class ContractorProfile:
    contractor: Contractor
    document_count: int
    raw_mapping_count: int


class GetContractorProfileUseCase:
    def __init__(
        self,
        *,
        contractors: ContractorRepository,
        mappings: RawContractorMappingRepository,
    ) -> None:
        self._contractors = contractors
        self._mappings = mappings

    async def execute(self, contractor_id: ContractorEntityId) -> ContractorProfile:
        contractor = await self._contractors.get(contractor_id)
        document_count = await self._contractors.count_documents_for(contractor_id)
        raw_mapping_count = await self._mappings.count_for(contractor_id)
        return ContractorProfile(
            contractor=contractor,
            document_count=document_count,
            raw_mapping_count=raw_mapping_count,
        )


__all__ = ["ContractorProfile", "GetContractorProfileUseCase"]
