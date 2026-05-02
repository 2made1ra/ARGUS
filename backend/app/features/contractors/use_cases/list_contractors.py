from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.ids import ContractorEntityId
from app.features.contractors.ports import ContractorRepository


@dataclass(frozen=True)
class ContractorCatalogItem:
    id: ContractorEntityId
    display_name: str
    normalized_key: str
    inn: str | None
    kpp: str | None
    document_count: int


class ListContractorsUseCase:
    def __init__(self, *, contractors: ContractorRepository) -> None:
        self._contractors = contractors

    async def execute(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
    ) -> list[ContractorCatalogItem]:
        contractors = await self._contractors.list(limit=limit, offset=offset, q=q)
        counts = await self._contractors.count_documents_for_many(
            [contractor.id for contractor in contractors],
        )
        return [
            ContractorCatalogItem(
                id=contractor.id,
                display_name=contractor.display_name,
                normalized_key=contractor.normalized_key,
                inn=contractor.inn,
                kpp=contractor.kpp,
                document_count=counts.get(contractor.id, 0),
            )
            for contractor in contractors
        ]


__all__ = ["ContractorCatalogItem", "ListContractorsUseCase"]
