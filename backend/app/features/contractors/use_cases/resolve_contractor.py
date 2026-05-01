from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import rapidfuzz.fuzz

from app.core.domain.ids import ContractorEntityId, DocumentId, new_contractor_entity_id
from app.core.ports.unit_of_work import UnitOfWork
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.entities.resolution import RawContractorMapping
from app.features.contractors.normalization import normalize_name
from app.features.contractors.ports import ContractorRepository, RawContractorMappingRepository
from app.features.ingest.ports import DocumentRepository, FieldsRepository


class ResolveContractorUseCase:
    def __init__(
        self,
        *,
        contractors: ContractorRepository,
        mappings: RawContractorMappingRepository,
        documents: DocumentRepository,
        fields: FieldsRepository,
        uow: UnitOfWork,
    ) -> None:
        self._contractors = contractors
        self._mappings = mappings
        self._documents = documents
        self._fields = fields
        self._uow = uow

    async def execute(self, document_id: DocumentId) -> ContractorEntityId | None:
        async with self._uow:
            await self._documents.get(document_id)
            contract_fields = await self._fields.get(document_id)

            raw_name = (contract_fields.supplier_name or "").strip() if contract_fields else ""
            inn_raw = (contract_fields.supplier_inn or "").strip() if contract_fields else ""
            inn: str | None = inn_raw or None

            if not raw_name:
                await self._documents.set_contractor_entity_id(document_id, None)
                await self._uow.commit()
                return None

            key = normalize_name(raw_name)

            resolved: Contractor | None = None
            confidence = 1.0

            if inn:
                resolved = await self._contractors.find_by_inn(inn)

            if resolved is None:
                resolved = await self._contractors.find_by_normalized_key(key)

            if resolved is None:
                pool = await self._contractors.find_all_for_fuzzy()
                if pool:
                    best = max(
                        pool,
                        key=lambda c: rapidfuzz.fuzz.token_sort_ratio(c.normalized_key, key),
                    )
                    score = rapidfuzz.fuzz.token_sort_ratio(best.normalized_key, key)
                    if score >= 90:
                        resolved = best
                        confidence = score / 100.0

            if resolved is None:
                resolved = Contractor(
                    id=new_contractor_entity_id(),
                    display_name=raw_name,
                    normalized_key=key,
                    inn=inn,
                    kpp=None,
                    created_at=datetime.now(UTC),
                )
                await self._contractors.add(resolved)
                confidence = 1.0

            await self._mappings.add(
                RawContractorMapping(
                    id=uuid4(),
                    raw_name=raw_name,
                    inn=inn,
                    contractor_entity_id=resolved.id,
                    confidence=confidence,
                )
            )

            await self._documents.set_contractor_entity_id(document_id, resolved.id)

            await self._uow.commit()
            return resolved.id


__all__ = ["ResolveContractorUseCase"]
