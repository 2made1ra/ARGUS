from pathlib import Path

import fitz

from sage.models import Page


def extract_text_pages(pdf_path: Path) -> list[Page]:
    pages: list[Page] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            pages.append(Page(index=index, text=text.strip(), kind="text"))
    return pages
