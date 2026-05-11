from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.adapters.sqlalchemy.models import (
    PriceImport as PriceImportModel,
)
from app.adapters.sqlalchemy.models import (
    PriceImportRow as PriceImportRowRow,
)
from app.adapters.sqlalchemy.models import PriceItem as PriceItemRow
from app.adapters.sqlalchemy.models import PriceItemSource as PriceItemSourceRow
from app.adapters.sqlalchemy.price_imports import SqlAlchemyPriceImportRepository
from app.adapters.sqlalchemy.price_items import SqlAlchemyPriceItemRepository
from app.features.catalog.entities.price_item import (
    PriceImport,
    PriceImportRow,
    PriceItem,
    PriceItemSource,
)
from app.features.catalog.ports import PriceItemNotFound
from sqlalchemy.ext.asyncio import AsyncSession


def _import_entity() -> PriceImport:
    return PriceImport(
        id=uuid4(),
        source_file_id=uuid4(),
        filename="prices.csv",
        source_path=None,
        file_sha256="hash",
        schema_version="prices_csv_v1",
        embedding_template_version="prices_v1",
        embedding_model="nomic-embed-text-v1.5",
        row_count=1,
        valid_row_count=1,
        invalid_row_count=0,
        status="IMPORTED",
        error_message=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _item_row() -> PriceItemRow:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return PriceItemRow(
        id=uuid4(),
        external_id="10",
        name="Аренда света",
        category="Аренда",
        category_normalized="аренда",
        unit="шт.",
        unit_normalized="шт",
        unit_price=Decimal("1200.00"),
        source_text="Описание",
        section="Свет",
        section_normalized="свет",
        supplier="ООО Ромашка",
        has_vat="Без НДС",
        vat_mode="without_vat",
        supplier_inn="7701234567",
        supplier_city="г. Москва",
        supplier_city_normalized="москва",
        supplier_phone="+7",
        supplier_email="info@example.com",
        supplier_status="Активен",
        supplier_status_normalized="активен",
        import_batch_id=uuid4(),
        source_file_id=uuid4(),
        source_import_row_id=uuid4(),
        row_fingerprint="fingerprint",
        is_active=True,
        superseded_at=None,
        embedding_text="Название: Аренда света",
        embedding_model="nomic-embed-text-v1.5",
        embedding_template_version="prices_v1",
        catalog_index_status="pending",
        embedding_error=None,
        indexing_error=None,
        indexed_at=None,
        legacy_embedding_present=True,
        legacy_embedding_dim=2,
        created_at=now,
        updated_at=now,
    )


def test_price_item_metadata_contains_duplicate_guard_index() -> None:
    index_names = {index.name for index in PriceItemRow.__table__.indexes}

    assert "ix_price_items_row_fingerprint_active" in index_names


@pytest.mark.asyncio
async def test_import_repository_adds_import_and_rows() -> None:
    session = AsyncMock()
    repository = SqlAlchemyPriceImportRepository(cast(AsyncSession, session))
    price_import = _import_entity()
    row = PriceImportRow(
        id=uuid4(),
        import_batch_id=price_import.id,
        source_file_id=price_import.source_file_id,
        row_number=2,
        raw={"name": "Аренда света"},
        normalized={"name": "Аренда света"},
        legacy_embedding_dim=2,
        legacy_embedding_present=True,
        validation_warnings=[],
        error_message=None,
        price_item_id=None,
        created_at=None,
    )

    await repository.add(price_import)
    await repository.add_row(row)

    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_import_repository_finds_imported_file_hash() -> None:
    row = PriceImportModel(
        id=uuid4(),
        source_file_id=uuid4(),
        filename="prices.csv",
        source_path=None,
        file_sha256="hash",
        schema_version="prices_csv_v1",
        embedding_template_version="prices_v1",
        embedding_model="nomic-embed-text-v1.5",
        row_count=1,
        valid_row_count=1,
        invalid_row_count=0,
        status="IMPORTED",
        error_message=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session = AsyncMock()
    session.scalar.return_value = row
    repository = SqlAlchemyPriceImportRepository(cast(AsyncSession, session))

    result = await repository.find_imported_by_file_sha256("hash")

    assert result is not None
    assert result.id == row.id
    statement = session.scalar.await_args.args[0]
    sql = str(statement.compile())
    assert "price_imports.file_sha256 = :file_sha256_1" in sql
    assert "price_imports.status = :status_1" in sql


@pytest.mark.asyncio
async def test_item_repository_lists_active_items() -> None:
    row = _item_row()
    session = AsyncMock()
    session.scalars.return_value = [row]
    repository = SqlAlchemyPriceItemRepository(cast(AsyncSession, session))

    result = await repository.list_active(limit=20, offset=10)

    assert len(result.items) == 1
    assert result.items[0].id == row.id
    assert result.total == 1
    statement = session.scalars.await_args.args[0]
    sql = str(statement.compile())
    assert "WHERE price_items.is_active IS true" in sql
    assert "LIMIT :param_1 OFFSET :param_2" in sql


@pytest.mark.asyncio
async def test_item_repository_gets_item_with_sources() -> None:
    item_row = _item_row()
    source_row = PriceItemSourceRow(
        id=uuid4(),
        price_item_id=item_row.id,
        source_kind="csv_import",
        import_batch_id=item_row.import_batch_id,
        source_file_id=item_row.source_file_id,
        price_import_row_id=item_row.source_import_row_id,
        source_text="Описание",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    import_row = PriceImportRowRow(
        id=item_row.source_import_row_id,
        import_batch_id=item_row.import_batch_id,
        source_file_id=item_row.source_file_id,
        row_number=42,
        raw={},
        normalized={},
        legacy_embedding_dim=None,
        legacy_embedding_present=False,
        validation_warnings=[],
        error_message=None,
        price_item_id=item_row.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session = AsyncMock()
    session.scalar.return_value = item_row
    session.execute.return_value = [(source_row, import_row.row_number)]
    repository = SqlAlchemyPriceItemRepository(cast(AsyncSession, session))

    detail = await repository.get_with_sources(item_row.id)

    assert detail.item.id == item_row.id
    assert len(detail.sources) == 1
    assert detail.sources[0].row_number == 42


@pytest.mark.asyncio
async def test_item_repository_get_with_sources_raises_when_missing() -> None:
    session = AsyncMock()
    session.scalar.return_value = None
    repository = SqlAlchemyPriceItemRepository(cast(AsyncSession, session))

    with pytest.raises(PriceItemNotFound):
        await repository.get_with_sources(uuid4())


@pytest.mark.asyncio
async def test_item_repository_adds_item_and_source() -> None:
    session = AsyncMock()
    repository = SqlAlchemyPriceItemRepository(cast(AsyncSession, session))
    row = _item_row()
    item = PriceItem(
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
        catalog_index_status=row.catalog_index_status,
        embedding_error=row.embedding_error,
        indexing_error=row.indexing_error,
        indexed_at=row.indexed_at,
        legacy_embedding_present=row.legacy_embedding_present,
        legacy_embedding_dim=row.legacy_embedding_dim,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    source = PriceItemSource(
        id=uuid4(),
        price_item_id=item.id,
        source_kind="csv_import",
        import_batch_id=item.import_batch_id,
        source_file_id=item.source_file_id,
        price_import_row_id=item.source_import_row_id,
        source_text=item.source_text,
        created_at=None,
    )

    await repository.add(item)
    await repository.add_source(source)

    assert session.execute.await_count == 2
