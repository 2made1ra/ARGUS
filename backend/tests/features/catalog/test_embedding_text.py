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
