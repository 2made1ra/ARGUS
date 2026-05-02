import shutil
from collections.abc import Callable, Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
import pytesseract
import pytest
from PIL import Image
from sage.pdf.ocr import OCR_DPI, OCR_LANG, ocr_pages


class FakePixmap:
    def tobytes(self, output: str) -> bytes:
        assert output == "png"
        buffer = BytesIO()
        Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
        return buffer.getvalue()


class FakePage:
    def __init__(self, index: int) -> None:
        self.index = index
        self.dpi_calls: list[int] = []

    def get_pixmap(self, *, dpi: int) -> FakePixmap:
        self.dpi_calls.append(dpi)
        return FakePixmap()


class FakeDocument:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages

    def __enter__(self) -> "FakeDocument":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def __iter__(self) -> Iterator[FakePage]:
        return iter(self.pages)


class FakeExecutor:
    max_workers: int | None = None

    def __init__(self, *, max_workers: int) -> None:
        type(self).max_workers = max_workers

    def __enter__(self) -> "FakeExecutor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def map(
        self,
        func: Callable[[tuple[int, Image.Image]], Any],
        items: list[tuple[int, Image.Image]],
    ) -> list[Any]:
        # Return deliberately reversed results to assert ocr_pages restores
        # stable page-index ordering after executor completion.
        return [func(item) for item in reversed(items)]


def test_ocr_pages_renders_300_dpi_and_returns_ordered_scan_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [FakePage(1), FakePage(2)]
    calls: list[tuple[tuple[int, int], str]] = []

    def fake_open(pdf_path: Path) -> FakeDocument:
        assert pdf_path == tmp_path / "scan.pdf"
        return FakeDocument(pages)

    def fake_image_to_string(image: Image.Image, *, lang: str) -> str:
        calls.append((image.size, lang))
        return f"text {len(calls)}"

    monkeypatch.setattr("sage.pdf.ocr.fitz.open", fake_open)
    monkeypatch.setattr(
        "sage.pdf.ocr.pytesseract.image_to_string", fake_image_to_string
    )
    monkeypatch.setattr("sage.pdf.ocr.os.cpu_count", lambda: 8)
    monkeypatch.setattr("sage.pdf.ocr.ThreadPoolExecutor", FakeExecutor)

    extracted = ocr_pages(tmp_path / "scan.pdf")

    assert FakeExecutor.max_workers == 8
    assert [page.dpi_calls for page in pages] == [[OCR_DPI], [OCR_DPI]]
    assert calls == [((1, 1), OCR_LANG), ((1, 1), OCR_LANG)]
    assert [page.model_dump() for page in extracted] == [
        {"index": 1, "text": "text 2", "kind": "scan"},
        {"index": 2, "text": "text 1", "kind": "scan"},
    ]


def test_ocr_pages_uses_fallback_worker_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_open(pdf_path: Path) -> FakeDocument:
        return FakeDocument([])

    monkeypatch.setattr("sage.pdf.ocr.fitz.open", fake_open)
    monkeypatch.setattr("sage.pdf.ocr.os.cpu_count", lambda: None)
    monkeypatch.setattr("sage.pdf.ocr.ThreadPoolExecutor", FakeExecutor)

    assert ocr_pages(tmp_path / "empty.pdf") == []
    assert FakeExecutor.max_workers == 2


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract is not installed")
def test_ocr_pages_smoke_with_real_tesseract(tmp_path: Path) -> None:
    pdf_path = tmp_path / "ocr-smoke.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 120), "Contract smoke test", fontsize=28)
    doc.save(pdf_path)
    doc.close()

    try:
        pages = ocr_pages(pdf_path)
    except pytesseract.TesseractError as exc:
        if "Failed loading language" in str(exc):
            pytest.skip("tesseract rus+eng language data is not installed")
        raise

    assert len(pages) == 1
    assert pages[0].index == 1
    assert pages[0].kind == "scan"
    assert "smoke" in pages[0].text.lower()
