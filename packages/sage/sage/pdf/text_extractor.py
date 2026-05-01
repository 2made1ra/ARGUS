from pathlib import Path

import fitz

from sage.models import Page


def extract_text_pages(pdf_path: Path) -> list[Page]:
    pages: list[Page] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            pages.append(Page(index=index, text=page.get_text(), kind="text"))
    return pages
