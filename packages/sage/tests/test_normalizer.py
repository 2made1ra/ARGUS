import pytest
from sage.models import Page
from sage.normalizer.clean import normalize_pages


def pages(*texts: str) -> list[Page]:
    return [
        Page(index=index, text=text, kind="text") for index, text in enumerate(texts, 1)
    ]


def normalized_texts(source_pages: list[Page]) -> list[str]:
    return [page.text for page in normalize_pages(source_pages)]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Договор\x00 оказания\x08 услуг", "Договор оказания услуг"),
        ("Цена\tдоговора\nсохранена", "Цена договора\nсохранена"),
        ("A\x1fB\x7fC\x9fD", "ABCD"),
    ],
)
def test_normalize_pages_removes_control_characters(
    source: str,
    expected: str,
) -> None:
    assert normalized_texts(pages(source)) == [expected]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Р”РѕРіРѕРІРѕСЂ", "Договор"),
        ("Ð”Ð¾Ð³Ð¾Ð²Ð¾Ñ€", "Договор"),
        ("ÐžÐžÐž Â«Ð Ð¾Ð¼Ð°ÑˆÐºÐ°Â» â„– 7", "ООО «Ромашка» № 7"),
    ],
)
def test_normalize_pages_repairs_common_mojibake(
    source: str,
    expected: str,
) -> None:
    assert normalized_texts(pages(source)) == [expected]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Договор     оказания\t\tуслуг", "Договор оказания услуг"),
        ("  Первая   строка  \n\tВторая\t строка  ", "Первая строка\nВторая строка"),
        ("Цена\u00a0договора\u2003согласована", "Цена договора согласована"),
    ],
)
def test_normalize_pages_collapses_whitespace_preserving_newlines(
    source: str,
    expected: str,
) -> None:
    assert normalized_texts(pages(source)) == [expected]


@pytest.mark.parametrize(
    ("source_pages", "expected"),
    [
        (
            pages(
                "ООО Аргус\nПолезный текст 1\nКонфиденциально",
                "ООО Аргус\nПолезный текст 2\nКонфиденциально",
                "ООО Аргус\nПолезный текст 3\nКонфиденциально",
            ),
            ["Полезный текст 1", "Полезный текст 2", "Полезный текст 3"],
        ),
        (
            pages(
                "Шапка\nАкт выполненных работ",
                "Шапка\nДоговор поставки",
                "Уникальная шапка\nСчет на оплату",
            ),
            [
                "Акт выполненных работ",
                "Договор поставки",
                "Уникальная шапка\nСчет на оплату",
            ],
        ),
        (
            pages(
                "Раздел 1\nСумма 100",
                "Раздел 2\nСумма 100",
                "Раздел 3\nСумма 100",
                "Раздел 4\nСумма 100",
            ),
            ["Раздел 1", "Раздел 2", "Раздел 3", "Раздел 4"],
        ),
    ],
)
def test_normalize_pages_removes_repeated_header_footer_lines(
    source_pages: list[Page],
    expected: list[str],
) -> None:
    assert normalized_texts(source_pages) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("--- Page 3 ---", "[PAGE 3]"),
        ("Страница 2 из 9", "[PAGE 2 OF 9]"),
        ("стр. 10/12", "[PAGE 10 OF 12]"),
    ],
)
def test_normalize_pages_normalizes_page_markers(
    source: str,
    expected: str,
) -> None:
    assert normalized_texts(pages(source)) == [expected]


def test_normalize_pages_removes_edo_noise_from_rules_file() -> None:
    source_pages = pages(
        "Договор оказания услуг\nДокумент подписан электронной подписью\nЦена 1000",
        "Подписано с использованием УКЭП\nАкт выполненных работ",
    )

    assert normalized_texts(source_pages) == [
        "Договор оказания услуг\nЦена 1000",
        "Акт выполненных работ",
    ]


def test_normalize_pages_returns_new_pages_without_reordering() -> None:
    source_pages = pages("  First  ", "  Second  ")

    result = normalize_pages(source_pages)

    assert [page.index for page in result] == [1, 2]
    assert [page.text for page in result] == ["First", "Second"]
    assert [page.text for page in source_pages] == ["  First  ", "  Second  "]
    assert result[0] is not source_pages[0]
