from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.features.catalog.dto import (
    FoundPriceItem,
    MatchReason,
    SearchPriceItemsFilters,
    SearchPriceItemsResult,
)
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


class CatalogSearchFiltersIn(BaseModel):
    supplier_city: str | None = None
    supplier_city_normalized: str | None = None
    category: str | None = None
    section: str | None = None
    supplier_status: str | None = None
    supplier_status_normalized: str | None = None
    has_vat: str | None = None
    vat_mode: str | None = None
    unit_price: Decimal | None = None
    unit_price_min: Decimal | None = None
    unit_price_max: Decimal | None = None

    def to_domain(self) -> SearchPriceItemsFilters:
        return SearchPriceItemsFilters(
            supplier_city=self.supplier_city,
            supplier_city_normalized=self.supplier_city_normalized,
            category=self.category,
            section=self.section,
            supplier_status=self.supplier_status,
            supplier_status_normalized=self.supplier_status_normalized,
            has_vat=self.has_vat,
            vat_mode=self.vat_mode,
            unit_price=self.unit_price,
            unit_price_min=self.unit_price_min,
            unit_price_max=self.unit_price_max,
        )


class CatalogSearchRequestIn(BaseModel):
    query: str
    limit: int = 10
    filters: CatalogSearchFiltersIn | None = None

    def filters_to_domain(self) -> SearchPriceItemsFilters:
        if self.filters is None:
            return SearchPriceItemsFilters()
        return self.filters.to_domain()


class MatchReasonOut(BaseModel):
    code: Literal[
        "semantic",
        "keyword_name",
        "keyword_supplier",
        "keyword_inn",
        "keyword_source_text",
        "keyword_external_id",
    ]
    label: str

    @classmethod
    def from_domain(cls, reason: MatchReason) -> MatchReasonOut:
        return cls(code=reason.code, label=reason.label)


class FoundPriceItemOut(BaseModel):
    id: UUID
    score: float
    name: str
    category: str | None
    unit: str
    unit_price: str
    supplier: str | None
    supplier_city: str | None
    source_text_snippet: str | None
    source_text_full_available: bool
    match_reason: MatchReasonOut

    @classmethod
    def from_domain(cls, item: FoundPriceItem) -> FoundPriceItemOut:
        return cls(
            id=item.id,
            score=item.score,
            name=item.name,
            category=item.category,
            unit=item.unit,
            unit_price=_decimal_string(item.unit_price),
            supplier=item.supplier,
            supplier_city=item.supplier_city,
            source_text_snippet=item.source_text_snippet,
            source_text_full_available=item.source_text_full_available,
            match_reason=MatchReasonOut.from_domain(item.match_reason),
        )


class CatalogSearchResultOut(BaseModel):
    items: list[FoundPriceItemOut]

    @classmethod
    def from_domain(cls, result: SearchPriceItemsResult) -> CatalogSearchResultOut:
        return cls(
            items=[FoundPriceItemOut.from_domain(item) for item in result.items],
        )


def _decimal_string(value: Decimal) -> str:
    return f"{value:.2f}"


__all__ = [
    "CatalogSearchRequestIn",
    "CatalogSearchResultOut",
    "FoundPriceItemOut",
    "MatchReasonOut",
    "PriceImportSummaryOut",
    "PriceItemDetailOut",
    "PriceItemListOut",
    "PriceItemOut",
    "PriceItemSourceOut",
]
