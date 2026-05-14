from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Contractor(Base):
    __tablename__ = "contractors"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    normalized_key: Mapped[str | None] = mapped_column(Text, unique=True)
    inn: Mapped[str | None] = mapped_column(Text, unique=True)
    kpp: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )


class ContractorRawMapping(Base):
    __tablename__ = "contractor_raw_mappings"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    raw_name: Mapped[str | None] = mapped_column(Text)
    inn: Mapped[str | None] = mapped_column(Text)
    contractor_entity_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("contractors.id", ondelete="CASCADE"),
    )
    confidence: Mapped[float | None] = mapped_column(Float)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    contractor_entity_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("contractors.id", ondelete="CASCADE"),
    )
    title: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    preview_file_path: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    document_kind: Mapped[str | None] = mapped_column(Text)
    doc_type: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    partial_extraction: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
    )
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section_type: Mapped[str | None] = mapped_column(Text)
    chunk_summary: Mapped[str | None] = mapped_column(Text)


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
    )
    fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )


class DocumentSummary(Base):
    __tablename__ = "document_summaries"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )


class PriceImport(Base):
    __tablename__ = "price_imports"
    __table_args__ = (
        Index(
            "ux_price_imports_file_sha256_not_null",
            "file_sha256",
            unique=True,
            postgresql_where=text("file_sha256 is not null"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    source_file_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True))
    filename: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str | None] = mapped_column(Text)
    file_sha256: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(
        Text,
        server_default=text("'prices_csv_v1'"),
    )
    embedding_template_version: Mapped[str] = mapped_column(
        Text,
        server_default=text("'prices_v1'"),
    )
    embedding_model: Mapped[str] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    valid_row_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    invalid_row_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class CatalogImportJob(Base):
    __tablename__ = "catalog_import_jobs"
    __table_args__ = (
        Index("ix_catalog_import_jobs_status", "status"),
        Index("ix_catalog_import_jobs_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    filename: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(Text)
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(Text)
    progress_percent: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    stage_progress_percent: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
    )
    row_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    valid_row_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    invalid_row_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    index_total: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    indexed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    embedding_failed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    indexing_failed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    skipped: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    import_batch_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True))
    source_file_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class PriceImportRow(Base):
    __tablename__ = "price_import_rows"
    __table_args__ = (
        Index("ix_price_import_rows_import_batch_id", "import_batch_id"),
        Index("ix_price_import_rows_price_item_id", "price_item_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    import_batch_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("price_imports.id", ondelete="CASCADE"),
    )
    source_file_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True))
    row_number: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)
    normalized: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    legacy_embedding_dim: Mapped[int | None] = mapped_column(Integer)
    legacy_embedding_present: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
    )
    validation_warnings: Mapped[list[str]] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    price_item_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("price_items.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )


class PriceItem(Base):
    __tablename__ = "price_items"
    __table_args__ = (
        Index(
            "ix_price_items_row_fingerprint_active",
            "row_fingerprint",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index("ix_price_items_catalog_index_status", "catalog_index_status"),
        Index("ix_price_items_supplier_city_normalized", "supplier_city_normalized"),
        Index("ix_price_items_category_normalized", "category_normalized"),
        Index(
            "ix_price_items_supplier_status_normalized",
            "supplier_status_normalized",
        ),
        Index("ix_price_items_supplier_inn", "supplier_inn"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    external_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    category_normalized: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    unit_normalized: Mapped[str | None] = mapped_column(Text)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    source_text: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text)
    section_normalized: Mapped[str | None] = mapped_column(Text)
    supplier: Mapped[str | None] = mapped_column(Text)
    has_vat: Mapped[str | None] = mapped_column(Text)
    vat_mode: Mapped[str | None] = mapped_column(Text)
    supplier_inn: Mapped[str | None] = mapped_column(Text)
    supplier_city: Mapped[str | None] = mapped_column(Text)
    supplier_city_normalized: Mapped[str | None] = mapped_column(Text)
    supplier_phone: Mapped[str | None] = mapped_column(Text)
    supplier_email: Mapped[str | None] = mapped_column(Text)
    supplier_status: Mapped[str | None] = mapped_column(Text)
    supplier_status_normalized: Mapped[str | None] = mapped_column(Text)
    import_batch_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("price_imports.id", ondelete="RESTRICT"),
    )
    source_file_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True))
    source_import_row_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("price_import_rows.id", ondelete="SET NULL"),
    )
    row_fingerprint: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    superseded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    embedding_text: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(Text)
    embedding_template_version: Mapped[str] = mapped_column(
        Text,
        server_default=text("'prices_v1'"),
    )
    catalog_index_status: Mapped[str] = mapped_column(Text)
    embedding_error: Mapped[str | None] = mapped_column(Text)
    indexing_error: Mapped[str | None] = mapped_column(Text)
    indexed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    legacy_embedding_present: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
    )
    legacy_embedding_dim: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )


class PriceItemSource(Base):
    __tablename__ = "price_item_sources"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    price_item_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("price_items.id", ondelete="CASCADE"),
    )
    source_kind: Mapped[str] = mapped_column(Text, server_default=text("'csv_import'"))
    import_batch_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("price_imports.id", ondelete="RESTRICT"),
    )
    source_file_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True))
    price_import_row_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("price_import_rows.id", ondelete="SET NULL"),
    )
    source_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
