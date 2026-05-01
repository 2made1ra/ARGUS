from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.domain.ids import ContractorEntityId


@dataclass
class RawContractorMapping:
    id: UUID
    raw_name: str
    inn: str | None
    contractor_entity_id: ContractorEntityId
    confidence: float


__all__ = ["RawContractorMapping"]
