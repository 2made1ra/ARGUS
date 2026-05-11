from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import PriceImportRow as PriceImportRowRow
from app.adapters.sqlalchemy.models import PriceItem as PriceItemRow
from app.adapters.sqlalchemy.models import PriceItemSource as PriceItemSourceRow
from app.features.catalog.entities.price_item import (
    PriceItem,
    PriceItemDetail,
    PriceItemList,
    PriceItemSource,
    PriceItemSourceRef,
)
from app.features.catalog.ports import PriceItemNotFound


class SqlAlchemyPriceItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: PriceItem) -> None:
        statement = insert(PriceItemRow).values(**_item_values(item))
        await self._session.execute(statement)

    async def add_source(self, source: PriceItemSource) -> None:
        statement = insert(PriceItemSourceRow).values(
            id=source.id,
            price_item_id=source.price_item_id,
            source_kind=source.source_kind,
            import_batch_id=source.import_batch_id,
            source_file_id=source.source_file_id,
            price_import_row_id=source.price_import_row_id,
            source_text=source.source_text,
            created_at=source.created_at,
        )
        await self._session.execute(statement)

    async def find_active_by_row_fingerprint(
        self,
        row_fingerprint: str,
    ) -> PriceItem | None:
        statement = select(PriceItemRow).where(
            PriceItemRow.row_fingerprint == row_fingerprint,
            PriceItemRow.is_active.is_(True),
        )
        row = await self._session.scalar(statement)
        return _item_to_entity(row) if row is not None else None

    async def list_active(self, *, limit: int, offset: int) -> PriceItemList:
        statement = (
            select(PriceItemRow)
            .where(PriceItemRow.is_active.is_(True))
            .order_by(PriceItemRow.created_at.desc(), PriceItemRow.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.scalars(statement)
        items = [_item_to_entity(row) for row in rows]

        count_statement = (
            select(func.count())
            .select_from(PriceItemRow)
            .where(PriceItemRow.is_active.is_(True))
        )
        total_value = await self._session.scalar(count_statement)
        total = total_value if isinstance(total_value, int) else len(items)
        return PriceItemList(items=items, total=total)

    async def list_active_for_indexing(self, *, limit: int) -> list[PriceItem]:
        statement = (
            select(PriceItemRow)
            .where(
                PriceItemRow.is_active.is_(True),
                PriceItemRow.catalog_index_status != "indexed",
            )
            .order_by(PriceItemRow.created_at.asc(), PriceItemRow.id.asc())
            .limit(limit)
        )
        rows = await self._session.scalars(statement)
        return [_item_to_entity(row) for row in rows]

    async def mark_indexed(
        self,
        item_id: UUID,
        *,
        embedding_model: str,
        embedding_template_version: str,
        indexed_at: datetime,
    ) -> None:
        statement = (
            update(PriceItemRow)
            .where(PriceItemRow.id == item_id)
            .values(
                embedding_model=embedding_model,
                embedding_template_version=embedding_template_version,
                catalog_index_status="indexed",
                embedding_error=None,
                indexing_error=None,
                indexed_at=indexed_at,
                updated_at=indexed_at,
            )
        )
        await self._session.execute(statement)

    async def mark_embedding_failed(self, item_id: UUID, *, error: str) -> None:
        statement = (
            update(PriceItemRow)
            .where(PriceItemRow.id == item_id)
            .values(
                catalog_index_status="embedding_failed",
                embedding_error=error,
                indexing_error=None,
                indexed_at=None,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(statement)

    async def mark_indexing_failed(self, item_id: UUID, *, error: str) -> None:
        statement = (
            update(PriceItemRow)
            .where(PriceItemRow.id == item_id)
            .values(
                catalog_index_status="indexing_failed",
                embedding_error=None,
                indexing_error=error,
                indexed_at=None,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(statement)

    async def get_with_sources(self, item_id: UUID) -> PriceItemDetail:
        item_statement = select(PriceItemRow).where(PriceItemRow.id == item_id)
        item_row = await self._session.scalar(item_statement)
        if item_row is None:
            raise PriceItemNotFound(item_id)

        sources_statement = (
            select(PriceItemSourceRow, PriceImportRowRow.row_number)
            .outerjoin(
                PriceImportRowRow,
                PriceItemSourceRow.price_import_row_id == PriceImportRowRow.id,
            )
            .where(PriceItemSourceRow.price_item_id == item_id)
            .order_by(PriceItemSourceRow.created_at.asc(), PriceItemSourceRow.id.asc())
        )
        result = await self._session.execute(sources_statement)
        sources = [
            PriceItemSourceRef(
                source_kind=source_row.source_kind,
                import_batch_id=source_row.import_batch_id,
                source_file_id=source_row.source_file_id,
                price_import_row_id=source_row.price_import_row_id,
                row_number=row_number,
                source_text=source_row.source_text,
            )
            for source_row, row_number in result
        ]
        return PriceItemDetail(item=_item_to_entity(item_row), sources=sources)


def _item_values(item: PriceItem) -> dict[str, object]:
    return {
        "id": item.id,
        "external_id": item.external_id,
        "name": item.name,
        "category": item.category,
        "category_normalized": item.category_normalized,
        "unit": item.unit,
        "unit_normalized": item.unit_normalized,
        "unit_price": item.unit_price,
        "source_text": item.source_text,
        "section": item.section,
        "section_normalized": item.section_normalized,
        "supplier": item.supplier,
        "has_vat": item.has_vat,
        "vat_mode": item.vat_mode,
        "supplier_inn": item.supplier_inn,
        "supplier_city": item.supplier_city,
        "supplier_city_normalized": item.supplier_city_normalized,
        "supplier_phone": item.supplier_phone,
        "supplier_email": item.supplier_email,
        "supplier_status": item.supplier_status,
        "supplier_status_normalized": item.supplier_status_normalized,
        "import_batch_id": item.import_batch_id,
        "source_file_id": item.source_file_id,
        "source_import_row_id": item.source_import_row_id,
        "row_fingerprint": item.row_fingerprint,
        "is_active": item.is_active,
        "superseded_at": item.superseded_at,
        "embedding_text": item.embedding_text,
        "embedding_model": item.embedding_model,
        "embedding_template_version": item.embedding_template_version,
        "catalog_index_status": item.catalog_index_status,
        "embedding_error": item.embedding_error,
        "indexing_error": item.indexing_error,
        "indexed_at": item.indexed_at,
        "legacy_embedding_present": item.legacy_embedding_present,
        "legacy_embedding_dim": item.legacy_embedding_dim,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _item_to_entity(row: PriceItemRow) -> PriceItem:
    return PriceItem(
        id=row.id,
        external_id=row.external_id,
        name=row.name,
        category=row.category,
        category_normalized=row.category_normalized,
        unit=row.unit,
        unit_normalized=row.unit_normalized,
        unit_price=row.unit_price,
        source_text=row.source_text,
        section=row.section,
        section_normalized=row.section_normalized,
        supplier=row.supplier,
        has_vat=row.has_vat,
        vat_mode=row.vat_mode,
        supplier_inn=row.supplier_inn,
        supplier_city=row.supplier_city,
        supplier_city_normalized=row.supplier_city_normalized,
        supplier_phone=row.supplier_phone,
        supplier_email=row.supplier_email,
        supplier_status=row.supplier_status,
        supplier_status_normalized=row.supplier_status_normalized,
        import_batch_id=row.import_batch_id,
        source_file_id=row.source_file_id,
        source_import_row_id=row.source_import_row_id,
        row_fingerprint=row.row_fingerprint,
        is_active=row.is_active,
        superseded_at=row.superseded_at,
        embedding_text=row.embedding_text,
        embedding_model=row.embedding_model,
        embedding_template_version=row.embedding_template_version,
        catalog_index_status=row.catalog_index_status,  # type: ignore[arg-type]
        embedding_error=row.embedding_error,
        indexing_error=row.indexing_error,
        indexed_at=row.indexed_at,
        legacy_embedding_present=row.legacy_embedding_present,
        legacy_embedding_dim=row.legacy_embedding_dim,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


__all__ = ["SqlAlchemyPriceItemRepository"]
