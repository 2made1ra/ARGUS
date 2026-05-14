from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

PriceImportStatus = Literal["QUEUED", "PROCESSING", "IMPORTED", "FAILED"]
CatalogIndexStatus = Literal[
    "pending",
    "indexed",
    "embedding_failed",
    "indexing_failed",
]


@dataclass(slots=True)
class PriceImport:
    id: UUID
    source_file_id: UUID
    filename: str
    source_path: str | None
    file_sha256: str | None
    schema_version: str
    embedding_template_version: str
    embedding_model: str
    row_count: int
    valid_row_count: int
    invalid_row_count: int
    status: PriceImportStatus
    error_message: str | None
    created_at: datetime | None
    completed_at: datetime | None


@dataclass(slots=True)
class PriceImportRow:
    id: UUID
    import_batch_id: UUID
    source_file_id: UUID
    row_number: int
    raw: dict[str, str]
    normalized: dict[str, object] | None
    legacy_embedding_dim: int | None
    legacy_embedding_present: bool
    validation_warnings: list[str]
    error_message: str | None
    price_item_id: UUID | None
    created_at: datetime | None


@dataclass(slots=True)
class PriceItem:
    id: UUID
    external_id: str | None
    name: str
    category: str | None
    category_normalized: str | None
    unit: str
    unit_normalized: str | None
    unit_price: Decimal
    source_text: str | None
    section: str | None
    section_normalized: str | None
    supplier: str | None
    has_vat: str | None
    vat_mode: str | None
    supplier_inn: str | None
    supplier_city: str | None
    supplier_city_normalized: str | None
    supplier_phone: str | None
    supplier_email: str | None
    supplier_status: str | None
    supplier_status_normalized: str | None
    import_batch_id: UUID
    source_file_id: UUID
    source_import_row_id: UUID | None
    row_fingerprint: str
    is_active: bool
    superseded_at: datetime | None
    embedding_text: str
    embedding_model: str
    embedding_template_version: str
    catalog_index_status: CatalogIndexStatus
    embedding_error: str | None
    indexing_error: str | None
    indexed_at: datetime | None
    legacy_embedding_present: bool
    legacy_embedding_dim: int | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(slots=True)
class PriceItemSource:
    id: UUID
    price_item_id: UUID
    source_kind: str
    import_batch_id: UUID
    source_file_id: UUID
    price_import_row_id: UUID | None
    source_text: str | None
    created_at: datetime | None


@dataclass(slots=True)
class PriceItemSourceRef:
    source_kind: str
    import_batch_id: UUID
    source_file_id: UUID
    price_import_row_id: UUID | None
    row_number: int | None
    source_text: str | None


@dataclass(slots=True)
class PriceItemDetail:
    item: PriceItem
    sources: list[PriceItemSourceRef]


@dataclass(slots=True)
class PriceItemList:
    items: list[PriceItem]
    total: int
    indexed_total: int


__all__ = [
    "CatalogIndexStatus",
    "PriceImport",
    "PriceImportRow",
    "PriceImportStatus",
    "PriceItem",
    "PriceItemDetail",
    "PriceItemList",
    "PriceItemSource",
    "PriceItemSourceRef",
]
