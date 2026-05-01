from __future__ import annotations

from app.core.domain.ids import ContractorEntityId
from app.features.contractors.ports import ContractorRepository
from app.features.ingest.entities.document import Document


class ListContractorDocumentsUseCase:
    def __init__(self, *, contractors: ContractorRepository) -> None:
        self._contractors = contractors

    async def execute(
        self,
        *,
        contractor_id: ContractorEntityId,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Document]:
        return await self._contractors.list_for_contractor(
            contractor_id,
            limit=limit,
            offset=offset,
        )


__all__ = ["ListContractorDocumentsUseCase"]
