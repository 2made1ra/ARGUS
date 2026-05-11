from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.features.catalog.entities.price_item import (
    PriceImport,
    PriceImportRow,
    PriceItem,
    PriceItemSource,
)
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase


class _FakeImportRepository:
    def __init__(self) -> None:
        self.imports: list[PriceImport] = []
        self.rows: list[PriceImportRow] = []

    async def add(self, price_import: PriceImport) -> None:
        self.imports.append(price_import)

    async def update(self, price_import: PriceImport) -> None:
        self.imports = [
            price_import if item.id == price_import.id else item
            for item in self.imports
        ]

    async def add_row(self, row: PriceImportRow) -> None:
        self.rows.append(row)

    async def update_row_item(self, row_id: UUID, item_id: UUID) -> None:
        for row in self.rows:
            if row.id == row_id:
                row.price_item_id = item_id

    async def find_imported_by_file_sha256(
        self,
        file_sha256: str,
    ) -> PriceImport | None:
        for price_import in self.imports:
            if (
                price_import.file_sha256 == file_sha256
                and price_import.status == "IMPORTED"
            ):
                return price_import
        return None


class _FakeItemRepository:
    def __init__(self) -> None:
        self.items: list[PriceItem] = []
        self.sources: list[PriceItemSource] = []

    async def add(self, item: PriceItem) -> None:
        self.items.append(item)

    async def add_source(self, source: PriceItemSource) -> None:
        self.sources.append(source)

    async def find_active_by_row_fingerprint(
        self,
        row_fingerprint: str,
    ) -> PriceItem | None:
        for item in self.items:
            if item.row_fingerprint == row_fingerprint and item.is_active:
                return item
        return None


class _FakeUoW:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    async def __aenter__(self) -> _FakeUoW:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


def _csv(rows: Sequence[str]) -> bytes:
    return (
        "id,name,category,unit,unit_price,source_text,created_at,section,supplier,"
        "has_vat,embedding,supplier_inn,supplier_city,supplier_phone,"
        "supplier_email,supplier_status\n"
        + "\n".join(rows)
        + "\n"
    ).encode()


def _catalog_row(
    *,
    external_id: str,
    name: str = "Монтаж",
    unit_price: str = "3500",
    created_at: str = "2026-01-01",
    city: str = "Москва",
) -> str:
    return (
        f"{external_id},{name},Работы,усл.,{unit_price},,{created_at},,"
        f"ООО,Без НДС,,7701234567,{city},+7,a@example.com,Активен"
    )


def _use_case() -> tuple[
    ImportPricesCsvUseCase,
    _FakeImportRepository,
    _FakeItemRepository,
    _FakeUoW,
]:
    imports = _FakeImportRepository()
    items = _FakeItemRepository()
    uow = _FakeUoW()
    return (
        ImportPricesCsvUseCase(imports=imports, items=items, uow=uow),
        imports,
        items,
        uow,
    )


async def test_import_prices_csv_stores_raw_rows_and_normalized_items() -> None:
    uc, imports, items, uow = _use_case()

    summary = await uc.execute(
        filename="prices.csv",
        content=_csv(
            [
                '10,Аренда света,Аренда,шт.,1200,"Описание\nстрока",'
                '2026-01-01,Свет,ООО Ромашка,Без НДС,"[0.1,0.2]",'
                "7701234567,г. Москва,+7,INFO@EXAMPLE.COM,Активен",
            ],
        ),
    )

    assert summary.status == "IMPORTED"
    assert summary.row_count == 1
    assert summary.valid_row_count == 1
    assert summary.invalid_row_count == 0
    assert summary.duplicate_file is False
    assert len(imports.imports) == 1
    assert len(imports.rows) == 1
    assert len(items.items) == 1
    assert len(items.sources) == 1
    row = imports.rows[0]
    item = items.items[0]
    assert row.import_batch_id == summary.id
    assert row.source_file_id == summary.source_file_id
    assert row.raw["embedding"] == "[0.1,0.2]"
    assert row.legacy_embedding_present is True
    assert row.legacy_embedding_dim == 2
    assert row.price_item_id == item.id
    assert item.external_id == "10"
    assert item.name == "Аренда света"
    assert item.source_text == "Описание\nстрока"
    assert item.legacy_embedding_present is True
    assert item.legacy_embedding_dim == 2
    assert item.embedding_template_version == "prices_v1"
    assert item.catalog_index_status == "pending"
    assert "Описание / источник: Описание\nстрока" in item.embedding_text
    assert item.source_import_row_id == row.id
    assert uow.commit_count == 1


async def test_import_prices_csv_returns_existing_summary_for_duplicate_file() -> None:
    uc, imports, items, _uow = _use_case()
    content = _csv(
        [
            "10,Аренда света,Аренда,шт.,1200,,2026-01-01,Свет,ООО,"
            "Без НДС,,7701234567,Москва,+7,a@example.com,Активен",
        ],
    )

    first = await uc.execute(filename="prices.csv", content=content)
    second = await uc.execute(filename="prices.csv", content=content)

    assert second.id == first.id
    assert second.duplicate_file is True
    assert len(imports.imports) == 1
    assert len(imports.rows) == 1
    assert len(items.items) == 1


async def test_import_prices_csv_links_repeated_fingerprint_to_existing_item() -> None:
    uc, imports, items, _uow = _use_case()

    first = await uc.execute(
        filename="first.csv",
        content=_csv([_catalog_row(external_id="1")]),
    )
    second = await uc.execute(
        filename="second.csv",
        content=_csv(
            [
                _catalog_row(
                    external_id="2",
                    name="  Монтаж ",
                    unit_price="3500.00",
                    created_at="2026-02-01",
                    city="г. Москва",
                ),
            ],
        ),
    )

    assert first.id != second.id
    assert len(imports.imports) == 2
    assert len(imports.rows) == 2
    assert len(items.items) == 1
    assert imports.rows[1].price_item_id == items.items[0].id
    assert len(items.sources) == 2


async def test_import_prices_csv_creates_new_item_when_price_changes() -> None:
    uc, _imports, items, _uow = _use_case()

    await uc.execute(
        filename="first.csv",
        content=_csv([_catalog_row(external_id="1")]),
    )
    await uc.execute(
        filename="second.csv",
        content=_csv(
            [
                _catalog_row(
                    external_id="1",
                    unit_price="4000",
                    created_at="2026-02-01",
                ),
            ],
        ),
    )

    assert len(items.items) == 2
    assert {str(item.unit_price) for item in items.items} == {"3500.00", "4000.00"}
