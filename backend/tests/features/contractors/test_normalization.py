from pathlib import Path

import pytest
from app.features.contractors import normalization
from app.features.contractors.normalization import (
    NormalizationRulesError,
    normalize_name,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ООО Вектор", "вектор"),
        ('ООО "Вектор"', "вектор"),
        ("АО Ромашка", "ромашка"),
        ("ИП Иванов", "иванов"),
        ("ПАО Газпром", "газпром"),
        ("ЗАО Нефть", "нефть"),
        ("НКО Добро", "добро"),
        ("Вектор ООО", "вектор"),
        ("Вектор, ООО", "вектор"),
        ("Завод ЗАО Технологий", "завод зао технологий"),
        ("ооо вектор", "вектор"),
        ("  лишние   пробелы  ", "лишние пробелы"),
        ("Вектор, Системы!", "вектор системы"),
        ("Иванов Иван", "иван иванов"),
        ("Иванов Иван Иванович", "иван иванов иванович"),
        (
            "Вектор Технологии Системы Интеграция",
            "вектор технологии системы интеграция",
        ),
        ("", ""),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_malformed_rules_raise_feature_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules_path = tmp_path / "normalization_rules.yaml"
    rules_path.write_text(
        "legal_forms: ООО\nstopwords: []\nblocklist: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(normalization, "_YAML_PATH", rules_path)
    normalization._load_rules.cache_clear()

    with pytest.raises(NormalizationRulesError):
        normalize_name("ООО Вектор")

    normalization._load_rules.cache_clear()
