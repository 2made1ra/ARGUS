from collections.abc import Iterator
from pathlib import Path

import pytest

from sage.pdf.detector import detect_kind
from sage.pdf.text_extractor import extract_text_pages


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[object, ...]] = []

    def get_text(self, *args: object) -> str:
        self.calls.append(args)
        return self.text


class FakeDocument:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages
        self.page_count = len(pages)

    def __enter__(self) -> "FakeDocument":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def __iter__(self) -> Iterator[FakePage]:
        return iter(self.pages)


@pytest.mark.parametrize(
    ("page_texts", "expected"),
    [
        (
            [
                "Договор оказания услуг " * 4,
                "Исполнитель оказывает услуги по заявке заказчика " * 3,
                "Стоимость услуг определяется счетом и актом " * 3,
            ],
            "text",
        ),
        (
            ["", "   ", "short"],
            "scan",
        ),
        (
            [
                "Передан через Диадок\nИдентификатор документа "
                "123e4567-e89b-12d3-a456-426614174000\n"
                "Страница 1 из 1\nПодпись соответствует\nСертификат",
                "СБИС\nGMT+5\nДоверенность\nКонтур\nСтраница 2 из 2",
            ],
            "scan",
        ),
    ],
)
def test_detect_kind_uses_sage_heuristics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    page_texts: list[str],
    expected: str,
) -> None:
    pages = [FakePage(text) for text in page_texts]

    def fake_open(pdf_path: Path) -> FakeDocument:
        assert pdf_path == tmp_path / "contract.pdf"
        return FakeDocument(pages)

    monkeypatch.setattr("sage.pdf.detector.fitz.open", fake_open)

    assert detect_kind(tmp_path / "contract.pdf") == expected
    assert all(page.calls == [("text",)] for page in pages)


def test_extract_text_pages_returns_text_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [FakePage("First page text"), FakePage("Second page text")]

    def fake_open(pdf_path: Path) -> FakeDocument:
        assert pdf_path == tmp_path / "contract.pdf"
        return FakeDocument(pages)

    monkeypatch.setattr("sage.pdf.text_extractor.fitz.open", fake_open)

    extracted = extract_text_pages(tmp_path / "contract.pdf")

    assert [page.model_dump() for page in extracted] == [
        {"index": 1, "text": "First page text", "kind": "text"},
        {"index": 2, "text": "Second page text", "kind": "text"},
    ]
    assert [page.calls for page in pages] == [[()], [()]]
