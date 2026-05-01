from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.domain.ids import ContractorEntityId


@dataclass
class Contractor:
    id: ContractorEntityId
    display_name: str
    normalized_key: str
    inn: str | None
    kpp: str | None
    created_at: datetime


__all__ = ["Contractor"]
