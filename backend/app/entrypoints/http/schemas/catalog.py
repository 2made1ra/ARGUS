from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.features.catalog.entities.price_item import PriceItem, PriceItemSourceRef
from app.features.catalog.use_cases.import_prices_csv import PriceImportSummary


class PriceImportSummaryOut(BaseModel):
    id: UUID
    source_file_id: UUID
    filename: str
    status: str
    row_count: int
    valid_row_count: int
    invalid_row_count: int
    embedding_template_version: str
    embedding_model: str
    duplicate_file: bool

    @classmethod
    def from_domain(cls, summary: PriceImportSummary) -> PriceImportSummaryOut:
        return cls(
            id=summary.id,
            source_file_id=summary.source_file_id,
            filename=summary.filename,
            status=summary.status,
            row_count=summary.row_count,
            valid_row_count=summary.valid_row_count,
            invalid_row_count=summary.invalid_row_count,
            embedding_template_version=summary.embedding_template_version,
            embedding_model=summary.embedding_model,
            duplicate_file=summary.duplicate_file,
        )


class PriceItemOut(BaseModel):
    id: UUID
    name: str
    category: str | None
    unit: str
    unit_price: str
    supplier: str | None
    supplier_inn: str | None
    supplier_city: str | None
    has_vat: str | None
    supplier_status: str | None
    catalog_index_status: str
    import_batch_id: UUID
    source_file_id: UUID

    @classmethod
    def from_domain(cls, item: PriceItem) -> PriceItemOut:
        return cls(
            id=item.id,
            name=item.name,
            category=item.category,
            unit=item.unit,
            unit_price=_decimal_string(item.unit_price),
            supplier=item.supplier,
            supplier_inn=item.supplier_inn,
            supplier_city=item.supplier_city,
            has_vat=item.has_vat,
            supplier_status=item.supplier_status,
            catalog_index_status=item.catalog_index_status,
            import_batch_id=item.import_batch_id,
            source_file_id=item.source_file_id,
        )


class PriceItemListOut(BaseModel):
    items: list[PriceItemOut]
    total: int


class PriceItemDetailItemOut(BaseModel):
    id: UUID
    external_id: str | None
    name: str
    category: str | None
    unit: str
    unit_price: str
    source_text: str | None
    section: str | None
    supplier: str | None
    supplier_city: str | None
    has_vat: str | None
    supplier_inn: str | None
    supplier_phone: str | None
    supplier_email: str | None
    supplier_status: str | None
    embedding_text: str
    embedding_template_version: str
    embedding_model: str
    catalog_index_status: str
    import_batch_id: UUID
    source_file_id: UUID

    @classmethod
    def from_domain(cls, item: PriceItem) -> PriceItemDetailItemOut:
        return cls(
            id=item.id,
            external_id=item.external_id,
            name=item.name,
            category=item.category,
            unit=item.unit,
            unit_price=_decimal_string(item.unit_price),
            source_text=item.source_text,
            section=item.section,
            supplier=item.supplier,
            supplier_city=item.supplier_city,
            has_vat=item.has_vat,
            supplier_inn=item.supplier_inn,
            supplier_phone=item.supplier_phone,
            supplier_email=item.supplier_email,
            supplier_status=item.supplier_status,
            embedding_text=item.embedding_text,
            embedding_template_version=item.embedding_template_version,
            embedding_model=item.embedding_model,
            catalog_index_status=item.catalog_index_status,
            import_batch_id=item.import_batch_id,
            source_file_id=item.source_file_id,
        )


class PriceItemSourceOut(BaseModel):
    source_kind: str
    import_batch_id: UUID
    source_file_id: UUID
    price_import_row_id: UUID | None
    row_number: int | None
    source_text: str | None

    @classmethod
    def from_domain(cls, source: PriceItemSourceRef) -> PriceItemSourceOut:
        return cls(
            source_kind=source.source_kind,
            import_batch_id=source.import_batch_id,
            source_file_id=source.source_file_id,
            price_import_row_id=source.price_import_row_id,
            row_number=source.row_number,
            source_text=source.source_text,
        )


class PriceItemDetailOut(BaseModel):
    item: PriceItemDetailItemOut
    sources: list[PriceItemSourceOut]


def _decimal_string(value: Decimal) -> str:
    return f"{value:.2f}"


__all__ = [
    "PriceImportSummaryOut",
    "PriceItemDetailOut",
    "PriceItemListOut",
    "PriceItemOut",
    "PriceItemSourceOut",
]

