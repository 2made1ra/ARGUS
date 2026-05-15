import pytest
from app.features.catalog.embedding_text import build_embedding_text


def test_build_embedding_text_uses_prices_v1_template() -> None:
    text = build_embedding_text(
        name="Аренда света",
        category="Аренда",
        section="Свет",
        source_text="Профессиональный комплект для сцены",
        unit="шт.",
    )

    assert text == "\n".join(
        [
            "Название: Аренда света",
            "Категория: Аренда",
            "Раздел: Свет",
            "Описание / источник: Профессиональный комплект для сцены",
            "Единица измерения: шт.",
        ],
    )


@pytest.mark.parametrize(
    "source_text",
    [
        "",
        "   ",
        "Ручной ввод",
        "ручной ввод",
        "  Аренда   света ",
    ],
)
def test_build_embedding_text_omits_non_meaningful_source_text(
    source_text: str,
) -> None:
    text = build_embedding_text(
        name="Аренда света",
        category="Аренда",
        section=None,
        source_text=source_text,
        unit="шт.",
    )

    assert "Описание / источник:" not in text


def test_build_embedding_text_omits_empty_lines_and_excluded_fields() -> None:
    text = build_embedding_text(
        name="Монтаж",
        category=None,
        section="",
        source_text="Основано на прайсе подрядчика",
        unit="усл.",
    )

    assert text == "\n".join(
        [
            "Название: Монтаж",
            "Описание / источник: Основано на прайсе подрядчика",
            "Единица измерения: усл.",
        ],
    )
    assert "unit_price" not in text
    assert "supplier_inn" not in text
    assert "embedding" not in text


def test_build_embedding_text_removes_tariff_suffix_from_name() -> None:
    text = build_embedding_text(
        name="Акустическая система 600 Вт (аренда за 1 день)",
        category="Аренда",
        section="Оборудование",
        source_text="Акустическая система 600 Вт",
        unit="день",
    )

    assert "Название: Акустическая система 600 Вт" in text
    assert "аренда за 1 день" not in text


def test_build_embedding_text_removes_tariff_pattern_before_tail() -> None:
    text = build_embedding_text(
        name=(
            "Проживание в гостевом доме (цена за 1 человека в день), "
            "база отдыха"
        ),
        category="Проживание",
        section=None,
        source_text=None,
        unit="чел",
    )

    assert "Название: Проживание в гостевом доме, база отдыха" in text
    assert "цена за 1 человека в день" not in text


def test_build_embedding_text_prefers_service_category_over_generic_category() -> None:
    text = build_embedding_text(
        name="Акустическая система 600 Вт",
        category="Аренда",
        service_category="звук",
        section="Оборудование",
        source_text=None,
        unit="день",
    )

    assert "Категория: звук" in text
    assert "Категория: Аренда" not in text
