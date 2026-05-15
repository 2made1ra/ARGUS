from __future__ import annotations

import re

_TARIFF_SUFFIX_RE = re.compile(
    r"\s*\((?:аренда|цена|услуга|стоимость)\s+за\s+[^)]*\)\s*$",
    re.IGNORECASE,
)


def build_embedding_text(
    *,
    name: str,
    category: str | None,
    section: str | None,
    source_text: str | None,
    unit: str,
) -> str:
    lines = [
        ("Название", _clean_name_for_embedding(name)),
        ("Категория", _clean_line_value(category)),
        ("Раздел", _clean_line_value(section)),
        (
            "Описание / источник",
            _clean_line_value(source_text)
            if _should_include_source_text(source_text, name)
            else None,
        ),
        ("Единица измерения", _clean_line_value(unit)),
    ]
    return "\n".join(f"{label}: {value}" for label, value in lines if value)


def source_text_is_meaningful(source_text: str | None, name: str) -> bool:
    return _should_include_source_text(source_text, name)


def _should_include_source_text(source_text: str | None, name: str) -> bool:
    if source_text is None or not source_text.strip():
        return False

    normalized_source = _normalize_for_compare(source_text)
    if normalized_source == _normalize_for_compare("Ручной ввод"):
        return False
    return normalized_source != _normalize_for_compare(name)


def _clean_line_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_name_for_embedding(name: str) -> str | None:
    return _clean_line_value(_TARIFF_SUFFIX_RE.sub("", name))


def _normalize_for_compare(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


__all__ = ["build_embedding_text", "source_text_is_meaningful"]
