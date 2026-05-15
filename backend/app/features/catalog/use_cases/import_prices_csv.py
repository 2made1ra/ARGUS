from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.domain.service_taxonomy import infer_service_category, is_generic_category
from app.features.catalog.csv_parser import ParsedPriceCsvRow, parse_price_csv
from app.features.catalog.embedding_text import build_embedding_text
from app.features.catalog.entities.price_item import (
    PriceImport,
    PriceImportRow,
    PriceItem,
    PriceItemSource,
)
from app.features.catalog.normalization import (
    NormalizedPriceRow,
    PriceRowValidationError,
    build_row_fingerprint,
    normalize_price_row,
)
from app.features.catalog.ports import (
    PriceImportRepository,
    PriceItemDuplicateFingerprint,
    PriceItemRepository,
    UnitOfWork,
)

SCHEMA_VERSION = "prices_csv_v1"
EMBEDDING_TEMPLATE_VERSION = "legacy_csv_embedding"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass(slots=True)
class PriceImportSummary:
    id: UUID
    source_file_id: UUID
    filename: str
    status: str
    row_count: int
    valid_row_count: int
    invalid_row_count: int
    embedding_template_version: str
    embedding_model: str
    duplicate_file: bool = False


@dataclass(slots=True)
class ImportPricesCsvProgress:
    total_rows: int
    processed_rows: int
    valid_row_count: int
    invalid_row_count: int
    import_batch_id: UUID | None
    source_file_id: UUID | None
    done: bool = False


type ImportPricesCsvProgressCallback = Callable[
    [ImportPricesCsvProgress],
    Awaitable[None],
]


class ImportPricesCsvUseCase:
    def __init__(
        self,
        *,
        imports: PriceImportRepository,
        items: PriceItemRepository,
        uow: UnitOfWork,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self._imports = imports
        self._items = items
        self._uow = uow
        self._embedding_model = embedding_model

    async def execute(
        self,
        *,
        filename: str,
        content: bytes,
        source_path: str | None = None,
        progress_callback: ImportPricesCsvProgressCallback | None = None,
    ) -> PriceImportSummary:
        file_sha256 = hashlib.sha256(content).hexdigest()

        now = datetime.now(UTC)
        import_batch = PriceImport(
            id=uuid4(),
            source_file_id=uuid4(),
            filename=filename,
            source_path=source_path,
            file_sha256=file_sha256,
            schema_version=SCHEMA_VERSION,
            embedding_template_version=EMBEDDING_TEMPLATE_VERSION,
            embedding_model=self._embedding_model,
            row_count=0,
            valid_row_count=0,
            invalid_row_count=0,
            status="PROCESSING",
            error_message=None,
            created_at=now,
            completed_at=None,
        )
        parsed_rows = parse_price_csv(content)

        async with self._uow:
            existing = await self._imports.find_imported_by_file_sha256(file_sha256)
            if existing is not None:
                return _summary(existing, duplicate_file=True)

            await self._imports.add(import_batch)
            valid_count = 0
            invalid_count = 0

            for parsed_row in parsed_rows:
                try:
                    normalized = normalize_price_row(parsed_row.raw)
                except PriceRowValidationError as exc:
                    invalid_count += 1
                    await self._imports.add_row(
                        _invalid_import_row(import_batch, parsed_row, str(exc)),
                    )
                    await _emit_progress(
                        progress_callback,
                        total_rows=len(parsed_rows),
                        processed_rows=valid_count + invalid_count,
                        valid_row_count=valid_count,
                        invalid_row_count=invalid_count,
                        import_batch_id=import_batch.id,
                        source_file_id=import_batch.source_file_id,
                    )
                    continue

                valid_count += 1
                import_row = _valid_import_row(import_batch, parsed_row, normalized)
                await self._imports.add_row(import_row)
                item = await self._get_or_create_item(
                    import_batch=import_batch,
                    import_row=import_row,
                    parsed_row=parsed_row,
                    normalized=normalized,
                )
                await self._imports.update_row_item(import_row.id, item.id)
                import_row.price_item_id = item.id
                await self._items.add_source(
                    PriceItemSource(
                        id=uuid4(),
                        price_item_id=item.id,
                        source_kind="csv_import",
                        import_batch_id=import_batch.id,
                        source_file_id=import_batch.source_file_id,
                        price_import_row_id=import_row.id,
                        source_text=normalized.source_text,
                        created_at=now,
                    ),
                )
                await _emit_progress(
                    progress_callback,
                    total_rows=len(parsed_rows),
                    processed_rows=valid_count + invalid_count,
                    valid_row_count=valid_count,
                    invalid_row_count=invalid_count,
                    import_batch_id=import_batch.id,
                    source_file_id=import_batch.source_file_id,
                )

            import_batch.row_count = len(parsed_rows)
            import_batch.valid_row_count = valid_count
            import_batch.invalid_row_count = invalid_count
            import_batch.status = "IMPORTED"
            import_batch.completed_at = datetime.now(UTC)
            await self._imports.update(import_batch)
            await _emit_progress(
                progress_callback,
                total_rows=len(parsed_rows),
                processed_rows=len(parsed_rows),
                valid_row_count=valid_count,
                invalid_row_count=invalid_count,
                import_batch_id=import_batch.id,
                source_file_id=import_batch.source_file_id,
                done=True,
            )
            await self._uow.commit()

        return _summary(import_batch)

    async def _get_or_create_item(
        self,
        *,
        import_batch: PriceImport,
        import_row: PriceImportRow,
        parsed_row: ParsedPriceCsvRow,
        normalized: NormalizedPriceRow,
    ) -> PriceItem:
        fingerprint = build_row_fingerprint(normalized)
        existing = await self._items.find_active_by_row_fingerprint(fingerprint)
        if existing is not None:
            return existing
        service_category = infer_service_category(normalized.category)
        category_enrichment_status = (
            "enriched"
            if service_category is not None
            else "pending"
            if is_generic_category(normalized.category)
            else "skipped"
        )
        service_category_source = (
            "deterministic" if service_category is not None else None
        )

        item = PriceItem(
            id=uuid4(),
            external_id=normalized.external_id,
            name=normalized.name,
            category=normalized.category,
            category_normalized=normalized.category_normalized,
            service_category=service_category,
            service_category_confidence=1.0 if service_category is not None else None,
            service_category_source=service_category_source,
            service_category_reason=(
                "source_category_alias" if service_category is not None else None
            ),
            category_enrichment_status=category_enrichment_status,
            category_enrichment_error=None,
            category_enriched_at=datetime.now(UTC)
            if service_category is not None
            else None,
            category_enrichment_model=None,
            category_enrichment_prompt_version=None,
            unit=normalized.unit,
            unit_normalized=normalized.unit_normalized,
            unit_price=normalized.unit_price,
            source_text=normalized.source_text,
            section=normalized.section,
            section_normalized=normalized.section_normalized,
            supplier=normalized.supplier,
            has_vat=normalized.has_vat,
            vat_mode=normalized.vat_mode,
            supplier_inn=normalized.supplier_inn,
            supplier_city=normalized.supplier_city,
            supplier_city_normalized=normalized.supplier_city_normalized,
            supplier_phone=normalized.supplier_phone,
            supplier_email=normalized.supplier_email,
            supplier_status=normalized.supplier_status,
            supplier_status_normalized=normalized.supplier_status_normalized,
            import_batch_id=import_batch.id,
            source_file_id=import_batch.source_file_id,
            source_import_row_id=import_row.id,
            row_fingerprint=fingerprint,
            is_active=True,
            superseded_at=None,
            embedding_text=build_embedding_text(
                name=normalized.name,
                category=normalized.category,
                service_category=service_category,
                section=normalized.section,
                source_text=normalized.source_text,
                unit=normalized.unit,
            ),
            embedding_model=import_batch.embedding_model,
            embedding_template_version=import_batch.embedding_template_version,
            catalog_index_status="pending",
            embedding_error=None,
            indexing_error=None,
            indexed_at=None,
            legacy_embedding_present=parsed_row.legacy_embedding_present,
            legacy_embedding_dim=parsed_row.legacy_embedding_dim,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        try:
            await self._items.add(item)
        except PriceItemDuplicateFingerprint:
            existing = await self._items.find_active_by_row_fingerprint(fingerprint)
            if existing is not None:
                return existing
            raise
        return item


def _valid_import_row(
    import_batch: PriceImport,
    parsed_row: ParsedPriceCsvRow,
    normalized: NormalizedPriceRow,
) -> PriceImportRow:
    return PriceImportRow(
        id=uuid4(),
        import_batch_id=import_batch.id,
        source_file_id=import_batch.source_file_id,
        row_number=parsed_row.row_number,
        raw=parsed_row.raw,
        normalized=normalized.to_json_dict(),
        legacy_embedding_dim=parsed_row.legacy_embedding_dim,
        legacy_embedding_present=parsed_row.legacy_embedding_present,
        validation_warnings=normalized.validation_warnings,
        error_message=None,
        price_item_id=None,
        created_at=datetime.now(UTC),
    )


def _invalid_import_row(
    import_batch: PriceImport,
    parsed_row: ParsedPriceCsvRow,
    error_message: str,
) -> PriceImportRow:
    return PriceImportRow(
        id=uuid4(),
        import_batch_id=import_batch.id,
        source_file_id=import_batch.source_file_id,
        row_number=parsed_row.row_number,
        raw=parsed_row.raw,
        normalized=None,
        legacy_embedding_dim=parsed_row.legacy_embedding_dim,
        legacy_embedding_present=parsed_row.legacy_embedding_present,
        validation_warnings=[],
        error_message=error_message,
        price_item_id=None,
        created_at=datetime.now(UTC),
    )


def _summary(
    price_import: PriceImport,
    *,
    duplicate_file: bool = False,
) -> PriceImportSummary:
    return PriceImportSummary(
        id=price_import.id,
        source_file_id=price_import.source_file_id,
        filename=price_import.filename,
        status=price_import.status,
        row_count=price_import.row_count,
        valid_row_count=price_import.valid_row_count,
        invalid_row_count=price_import.invalid_row_count,
        embedding_template_version=price_import.embedding_template_version,
        embedding_model=price_import.embedding_model,
        duplicate_file=duplicate_file,
    )


async def _emit_progress(
    callback: ImportPricesCsvProgressCallback | None,
    *,
    total_rows: int,
    processed_rows: int,
    valid_row_count: int,
    invalid_row_count: int,
    import_batch_id: UUID | None,
    source_file_id: UUID | None,
    done: bool = False,
) -> None:
    if callback is None:
        return
    await callback(
        ImportPricesCsvProgress(
            total_rows=total_rows,
            processed_rows=processed_rows,
            valid_row_count=valid_row_count,
            invalid_row_count=invalid_row_count,
            import_batch_id=import_batch_id,
            source_file_id=source_file_id,
            done=done,
        ),
    )


__all__ = [
    "ImportPricesCsvProgress",
    "ImportPricesCsvProgressCallback",
    "ImportPricesCsvUseCase",
    "PriceImportSummary",
]
