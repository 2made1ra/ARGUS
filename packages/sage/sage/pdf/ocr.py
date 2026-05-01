import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from sage.models import Page

OCR_DPI = 300
OCR_LANG = "rus+eng"


def _pixmap_to_image(pix: fitz.Pixmap) -> Image.Image:
    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def _ocr_image(item: tuple[int, Image.Image]) -> Page:
    index, image = item
    text = pytesseract.image_to_string(image, lang=OCR_LANG)
    return Page(index=index, text=text, kind="scan")


def ocr_pages(pdf_path: Path) -> list[Page]:
    rendered_pages: list[tuple[int, Image.Image]] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=OCR_DPI)
            rendered_pages.append((index, _pixmap_to_image(pix)))

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as executor:
        pages = list(executor.map(_ocr_image, rendered_pages))

    return sorted(pages, key=lambda page: page.index)
