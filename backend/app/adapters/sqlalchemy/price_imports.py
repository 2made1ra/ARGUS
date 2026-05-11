from __future__ import annotations

from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import PriceImport as PriceImportModel
from app.adapters.sqlalchemy.models import PriceImportRow as PriceImportRowModel
from app.features.catalog.entities.price_item import PriceImport, PriceImportRow


class SqlAlchemyPriceImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, price_import: PriceImport) -> None:
        statement = insert(PriceImportModel).values(**_import_values(price_import))
        await self._session.execute(statement)

    async def update(self, price_import: PriceImport) -> None:
        statement = (
            update(PriceImportModel)
            .where(PriceImportModel.id == price_import.id)
            .values(**_import_values(price_import))
        )
        await self._session.execute(statement)

    async def add_row(self, row: PriceImportRow) -> None:
        statement = insert(PriceImportRowModel).values(
            id=row.id,
            import_batch_id=row.import_batch_id,
            source_file_id=row.source_file_id,
            row_number=row.row_number,
            raw=row.raw,
            normalized=row.normalized,
            legacy_embedding_dim=row.legacy_embedding_dim,
            legacy_embedding_present=row.legacy_embedding_present,
            validation_warnings=row.validation_warnings,
            error_message=row.error_message,
            price_item_id=row.price_item_id,
            created_at=row.created_at,
        )
        await self._session.execute(statement)

    async def update_row_item(self, row_id: UUID, item_id: UUID) -> None:
        statement = (
            update(PriceImportRowModel)
            .where(PriceImportRowModel.id == row_id)
            .values(price_item_id=item_id)
        )
        await self._session.execute(statement)

    async def find_imported_by_file_sha256(
        self,
        file_sha256: str,
    ) -> PriceImport | None:
        statement = select(PriceImportModel).where(
            PriceImportModel.file_sha256 == file_sha256,
            PriceImportModel.status == "IMPORTED",
        )
        row = await self._session.scalar(statement)
        return _import_to_entity(row) if row is not None else None


def _import_values(price_import: PriceImport) -> dict[str, object]:
    return {
        "id": price_import.id,
        "source_file_id": price_import.source_file_id,
        "filename": price_import.filename,
        "source_path": price_import.source_path,
        "file_sha256": price_import.file_sha256,
        "schema_version": price_import.schema_version,
        "embedding_template_version": price_import.embedding_template_version,
        "embedding_model": price_import.embedding_model,
        "row_count": price_import.row_count,
        "valid_row_count": price_import.valid_row_count,
        "invalid_row_count": price_import.invalid_row_count,
        "status": price_import.status,
        "error_message": price_import.error_message,
        "created_at": price_import.created_at,
        "completed_at": price_import.completed_at,
    }


def _import_to_entity(row: PriceImportModel) -> PriceImport:
    return PriceImport(
        id=row.id,
        source_file_id=row.source_file_id,
        filename=row.filename,
        source_path=row.source_path,
        file_sha256=row.file_sha256,
        schema_version=row.schema_version,
        embedding_template_version=row.embedding_template_version,
        embedding_model=row.embedding_model,
        row_count=row.row_count,
        valid_row_count=row.valid_row_count,
        invalid_row_count=row.invalid_row_count,
        status=row.status,  # type: ignore[arg-type]
        error_message=row.error_message,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


__all__ = ["SqlAlchemyPriceImportRepository"]
