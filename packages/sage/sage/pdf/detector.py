import re
import statistics
from pathlib import Path
from typing import Literal

import fitz

PDFKind = Literal["text", "scan"]

TEXT_PDF_MIN_CHARS_PER_PAGE = 50

# Patterns that appear on EDI wrapper pages (Diadoc, SBIS, etc.) but carry
# no contract content. Stripped before measuring meaningful text length.
_EDO_NOISE = re.compile(
    r"(передан через|диадок|сбис|контур|идентификатор документа"
    r"|страница \d+ из \d+|подпись соответствует|сертификат|доверенность"
    r"|gmt\+|gmt-|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b)",
    re.IGNORECASE,
)


def _content_len(raw: str) -> int:
    """Return char count after stripping EDI noise and whitespace."""
    lines = [line for line in raw.splitlines() if not _EDO_NOISE.search(line)]
    return len(" ".join(lines).strip())


def detect_kind(pdf_path: Path) -> PDFKind:
    """Classify PDF as text or scan using SAGE text-layer heuristics."""
    with fitz.open(pdf_path) as doc:
        if doc.page_count == 0:
            return "scan"
        lengths = [_content_len(page.get_text("text") or "") for page in doc]

    if not any(lengths):
        return "scan"

    median = statistics.median(lengths)
    mean = sum(lengths) / len(lengths)
    pages_above = sum(1 for length in lengths if length >= TEXT_PDF_MIN_CHARS_PER_PAGE)
    fraction_above = pages_above / len(lengths)

    is_text = (
        median >= TEXT_PDF_MIN_CHARS_PER_PAGE
        and mean >= TEXT_PDF_MIN_CHARS_PER_PAGE
        and fraction_above >= 0.5
    )
    return "text" if is_text else "scan"
