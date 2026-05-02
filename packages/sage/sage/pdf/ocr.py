import io
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from sage.models import Page

OCR_DPI = 300
OCR_LANG = "rus+eng"


class OcrError(RuntimeError):
    pass


def _pixmap_to_image(pix: fitz.Pixmap) -> Image.Image:
    return Image.open(io.BytesIO(pix.tobytes("png")))


def _ocr_image(item: tuple[int, Image.Image]) -> Page:
    index, image = item
    try:
        text = pytesseract.image_to_string(image, lang=OCR_LANG) or ""
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrError(
            "OCR requires the system tesseract binary in PATH. "
            "Install Tesseract with Russian and English language data, "
            "or run the Celery worker in the Docker image.",
        ) from exc
    except pytesseract.TesseractError as exc:
        if "Failed loading language" in str(exc):
            raise OcrError(
                f"OCR requires Tesseract language data for {OCR_LANG}. "
                "Install Russian and English language packs, or run the "
                "Celery worker in the Docker image.",
            ) from exc
        raise
    return Page(index=index, text=text, kind="scan")


def ocr_pages(pdf_path: Path) -> list[Page]:
    if shutil.which("tesseract") is None:
        raise OcrError(
            "OCR requires the system tesseract binary in PATH. "
            "Install Tesseract with Russian and English language data, "
            "or run the Celery worker in the Docker image.",
        )

    rendered_pages: list[tuple[int, Image.Image]] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=OCR_DPI)
            rendered_pages.append((index, _pixmap_to_image(pix)))

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as executor:
        pages = list(executor.map(_ocr_image, rendered_pages))

    return sorted(pages, key=lambda page: page.index)
