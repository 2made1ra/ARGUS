from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


class PriceRowValidationError(ValueError):
    pass


@dataclass(slots=True)
class NormalizedPriceRow:
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
    vat_mode: str
    supplier_inn: str | None
    supplier_city: str | None
    supplier_city_normalized: str | None
    supplier_phone: str | None
    supplier_email: str | None
    supplier_status: str | None
    supplier_status_normalized: str | None
    validation_warnings: list[str]

    def to_json_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["unit_price"] = _decimal_to_string(self.unit_price)
        return data


def normalize_price_row(raw: Mapping[str, str]) -> NormalizedPriceRow:
    warnings: list[str] = []
    name = _required_text(raw.get("name"), "name")
    unit = _required_text(raw.get("unit"), "unit")
    unit_price = _parse_price(raw.get("unit_price"))
    supplier_inn = _normalize_inn(raw.get("supplier_inn"))
    if supplier_inn and len(supplier_inn) not in {10, 12}:
        warnings.append("supplier_inn has unusual length")

    return NormalizedPriceRow(
        external_id=_optional_text(raw.get("id")),
        name=name,
        category=_optional_text(raw.get("category")),
        category_normalized=_normalize_key(raw.get("category")),
        unit=unit,
        unit_normalized=_normalize_unit(unit),
        unit_price=unit_price,
        source_text=_optional_source_text(raw.get("source_text")),
        section=_optional_text(raw.get("section")),
        section_normalized=_normalize_key(raw.get("section")),
        supplier=_optional_text(raw.get("supplier")),
        has_vat=_optional_text(raw.get("has_vat")),
        vat_mode=_vat_mode(raw.get("has_vat")),
        supplier_inn=supplier_inn,
        supplier_city=_optional_text(raw.get("supplier_city")),
        supplier_city_normalized=_normalize_city(raw.get("supplier_city")),
        supplier_phone=_optional_text(raw.get("supplier_phone")),
        supplier_email=_normalize_email(raw.get("supplier_email")),
        supplier_status=_optional_text(raw.get("supplier_status")),
        supplier_status_normalized=_normalize_key(raw.get("supplier_status")),
        validation_warnings=warnings,
    )


def build_row_fingerprint(row: NormalizedPriceRow) -> str:
    payload = {
        "name": _normalize_for_compare(row.name),
        "category_normalized": row.category_normalized,
        "unit_normalized": row.unit_normalized,
        "unit_price": _decimal_to_string(row.unit_price),
        "supplier": _normalize_for_compare(row.supplier or ""),
        "supplier_inn": row.supplier_inn,
        "supplier_city_normalized": row.supplier_city_normalized,
        "source_text": _normalize_for_compare(row.source_text or ""),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required_text(value: str | None, field_name: str) -> str:
    normalized = _optional_text(value)
    if normalized is None:
        raise PriceRowValidationError(f"{field_name} is required")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = re.sub(r"\s+", " ", value.strip())
    return collapsed or None


def _optional_source_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_key(value: str | None) -> str | None:
    text = _optional_text(value)
    return text.casefold() if text is not None else None


def _normalize_unit(value: str | None) -> str | None:
    text = _normalize_key(value)
    if text is None:
        return None
    compact = text.removesuffix(".")
    if compact in {"шт", "ед", "nos", "pcs"}:
        return "шт"
    if compact in {"rnm", "сутки", "ночь", "ночи", "night"}:
        return "ночь"
    if compact in {"sqm", "кв.м", "кв м", "м2", "м²"}:
        return "м2"
    if compact in {"усл", "услуга"}:
        return "усл"
    return compact


def _parse_price(value: str | None) -> Decimal:
    if value is None or not value.strip():
        raise PriceRowValidationError("unit_price is required")
    normalized = value.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    try:
        parsed = Decimal(normalized)
    except InvalidOperation as exc:
        raise PriceRowValidationError("unit_price must be numeric") from exc
    return parsed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _vat_mode(value: str | None) -> str:
    text = _normalize_key(value)
    if not text:
        return "unknown"
    if "усн" in text or ("ндс" in text and "не облага" in text):
        return "without_vat"
    if "без" in text and "ндс" in text:
        return "without_vat"
    if "ндс" in text or "vat" in text:
        return "with_vat"
    return "unknown"


def _normalize_inn(value: str | None) -> str | None:
    digits = re.sub(r"\D+", "", value or "")
    return digits or None


def _normalize_city(value: str | None) -> str | None:
    text = _normalize_key(value)
    if text is None:
        return None
    text = re.sub(r"^(г\.?|город)\s+", "", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+г$", "", text)
    if text in {"санкт-петербург", "питер", "спб", "санкт петербург"}:
        return "санкт-петербург"
    if text in {"dubai, united arab emirates", "dubai, uae", "dubai"}:
        return "дубай"
    return text or None


def _normalize_email(value: str | None) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
        return text.casefold()
    return text


def _normalize_for_compare(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _decimal_to_string(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


__all__ = [
    "NormalizedPriceRow",
    "PriceRowValidationError",
    "build_row_fingerprint",
    "normalize_price_row",
]
