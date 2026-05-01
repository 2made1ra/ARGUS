from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

import rapidfuzz.fuzz
import rapidfuzz.process

from app.core.domain.ids import (
    ContractorEntityId,
    DocumentId,
    new_contractor_entity_id,
)
from app.core.ports.unit_of_work import UnitOfWork
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.entities.resolution import RawContractorMapping
from app.features.contractors.normalization import normalize_name
from app.features.contractors.ports import (
    ContractorRepository,
    RawContractorMappingRepository,
)
from app.features.ingest.entities.document import DocumentStatus
from app.features.ingest.ports import DocumentRepository, FieldsRepository

FUZZY_MATCH_THRESHOLD = 90
logger = logging.getLogger(__name__)


class InvalidDocumentStatusForResolution(Exception):
    def __init__(self, document_id: DocumentId, status: DocumentStatus) -> None:
        super().__init__(
            "Cannot resolve contractor for document "
            f"{document_id}: expected RESOLVING, got {status.value}"
        )
        self.document_id = document_id
        self.status = status


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
            document = await self._documents.get(document_id)
            if document.status is not DocumentStatus.RESOLVING:
                raise InvalidDocumentStatusForResolution(document_id, document.status)

            contract_fields = await self._fields.get(document_id)

            raw_name = (
                (contract_fields.supplier_name or "").strip() if contract_fields else ""
            )
            inn_raw = (
                (contract_fields.supplier_inn or "").strip() if contract_fields else ""
            )
            inn: str | None = inn_raw or None
            kpp_raw = (
                (contract_fields.supplier_kpp or "").strip() if contract_fields else ""
            )
            kpp: str | None = kpp_raw or None

            if not raw_name:
                await self._documents.set_contractor_entity_id(document_id, None)
                await self._uow.commit()
                logger.info(
                    "contractor_resolution_skipped",
                    extra={
                        "document_id": str(document_id),
                        "reason": "empty_raw_name",
                    },
                )
                return None

            key = normalize_name(raw_name)

            resolved: Contractor | None = None
            confidence = 1.0
            branch = "created"
            fuzzy_pool_size = 0

            if inn:
                resolved = await self._contractors.find_by_inn(inn)
                if resolved is not None:
                    branch = "inn"

            if resolved is None:
                resolved = await self._contractors.find_by_normalized_key(key)
                if resolved is not None:
                    branch = "normalized_key"

            if resolved is None:
                pool = await self._contractors.find_all_for_fuzzy()
                fuzzy_pool_size = len(pool)
                choices = {
                    index: contractor.normalized_key
                    for index, contractor in enumerate(pool)
                }
                match = rapidfuzz.process.extractOne(
                    key,
                    choices,
                    scorer=rapidfuzz.fuzz.token_sort_ratio,
                )
                if match is not None:
                    _, score, pool_index = match
                    best = pool[pool_index]
                    if score >= FUZZY_MATCH_THRESHOLD:
                        resolved = best
                        confidence = score / 100.0
                        branch = "fuzzy"

            if resolved is None:
                resolved = Contractor(
                    id=new_contractor_entity_id(),
                    display_name=raw_name,
                    normalized_key=key,
                    inn=inn,
                    kpp=kpp,
                    created_at=datetime.now(UTC),
                )
                await self._contractors.add(resolved)
                confidence = 1.0
                branch = "created"

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
            logger.info(
                "contractor_resolved",
                extra={
                    "document_id": str(document_id),
                    "contractor_entity_id": str(resolved.id),
                    "branch": branch,
                    "confidence": confidence,
                    "has_inn": inn is not None,
                    "fuzzy_pool_size": fuzzy_pool_size,
                },
            )
            return resolved.id


__all__ = [
    "FUZZY_MATCH_THRESHOLD",
    "InvalidDocumentStatusForResolution",
    "ResolveContractorUseCase",
]
