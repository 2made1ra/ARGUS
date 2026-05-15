from decimal import Decimal

import pytest
from app.features.catalog.normalization import (
    PriceRowValidationError,
    build_row_fingerprint,
    normalize_price_row,
)


def _raw(**overrides: str) -> dict[str, str]:
    row = {
        "id": "csv-1",
        "name": "  Аренда   света  ",
        "category": " Аренда ",
        "unit": "шт.",
        "unit_price": "1 234,50",
        "source_text": " Ручной ввод ",
        "section": " Свет ",
        "supplier": " ООО Ромашка ",
        "has_vat": "Без НДС",
        "supplier_inn": "77-01-23-45-67",
        "supplier_city": " г. Москва ",
        "supplier_phone": " +7 900 000 ",
        "supplier_email": " INFO@EXAMPLE.COM ",
        "supplier_status": " Активен ",
    }
    row.update(overrides)
    return row


def test_normalize_price_row_collapses_text_and_parses_price() -> None:
    normalized = normalize_price_row(_raw())

    assert normalized.external_id == "csv-1"
    assert normalized.name == "Аренда света"
    assert normalized.category == "Аренда"
    assert normalized.category_normalized == "аренда"
    assert normalized.unit == "шт."
    assert normalized.unit_normalized == "шт"
    assert normalized.unit_price == Decimal("1234.50")
    assert normalized.section_normalized == "свет"
    assert normalized.supplier == "ООО Ромашка"
    assert normalized.vat_mode == "without_vat"
    assert normalized.supplier_inn == "7701234567"
    assert normalized.supplier_city_normalized == "москва"
    assert normalized.supplier_email == "info@example.com"
    assert normalized.supplier_status_normalized == "активен"
    assert normalized.validation_warnings == []


@pytest.mark.parametrize(
    ("raw_vat", "vat_mode"),
    [
        ("Включая НДС", "with_vat"),
        ("НДС 20%", "with_vat"),
        ("Без НДС", "without_vat"),
        ("", "unknown"),
    ],
)
def test_normalize_price_row_derives_vat_mode(raw_vat: str, vat_mode: str) -> None:
    normalized = normalize_price_row(_raw(has_vat=raw_vat))

    assert normalized.vat_mode == vat_mode


@pytest.mark.parametrize(
    ("raw_city", "normalized_city"),
    [
        ("г. Санкт - Петербург", "санкт-петербург"),
        ("Санкт-Петербург г", "санкт-петербург"),
        ("Питер", "санкт-петербург"),
        ("Г ОДИНЦОВО", "одинцово"),
    ],
)
def test_normalize_price_row_canonicalizes_city_aliases(
    raw_city: str,
    normalized_city: str,
) -> None:
    normalized = normalize_price_row(_raw(supplier_city=raw_city))

    assert normalized.supplier_city_normalized == normalized_city


@pytest.mark.parametrize(
    ("raw_unit", "normalized_unit"),
    [
        ("Nos", "шт"),
        ("ед.", "шт"),
        ("Rnm", "ночь"),
        ("Sqm", "м2"),
    ],
)
def test_normalize_price_row_canonicalizes_unit_aliases(
    raw_unit: str,
    normalized_unit: str,
) -> None:
    normalized = normalize_price_row(_raw(unit=raw_unit))

    assert normalized.unit_normalized == normalized_unit


def test_normalize_price_row_warns_for_unusual_inn_length() -> None:
    normalized = normalize_price_row(_raw(supplier_inn="12345"))

    assert normalized.supplier_inn == "12345"
    assert "supplier_inn has unusual length" in normalized.validation_warnings


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("name", "", "name is required"),
        ("unit", "  ", "unit is required"),
        ("unit_price", "не число", "unit_price must be numeric"),
    ],
)
def test_normalize_price_row_rejects_required_invalid_fields(
    field: str,
    value: str,
    match: str,
) -> None:
    with pytest.raises(PriceRowValidationError, match=match):
        normalize_price_row(_raw(**{field: value}))


def test_build_row_fingerprint_uses_normalized_catalog_facts() -> None:
    first = normalize_price_row(_raw(id="first", unit_price="1 234,50"))
    second = normalize_price_row(_raw(id="second", unit_price="1234.5"))

    assert build_row_fingerprint(first) == build_row_fingerprint(second)
