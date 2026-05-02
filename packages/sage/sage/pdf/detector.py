import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import fitz

PDFKind = Literal["text", "scan"]


@dataclass(frozen=True)
class DetectorConfig:
    min_chars_per_page: int = 50
    min_text_page_ratio: float = 0.5
    edo_noise_max_ratio: float = 0.8


# Patterns that appear on EDI wrapper pages (Diadoc, SBIS, etc.) but carry
# no contract content. Stripped before measuring meaningful text length.
_EDO_NOISE = re.compile(
    r"(передан через|диадок|сбис|контур|идентификатор документа"
    r"|страница \d+ из \d+|подпись соответствует|сертификат|доверенность"
    r"|gmt\+|gmt-|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b)",
    re.IGNORECASE,
)


def _content_len(raw: str, config: DetectorConfig) -> int:
    """Return char count after stripping EDI noise and whitespace."""
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        return 0

    content_lines = [line for line in lines if not _EDO_NOISE.search(line)]
    noise_ratio = (len(lines) - len(content_lines)) / len(lines)
    if noise_ratio > config.edo_noise_max_ratio:
        return 0

    return len(" ".join(content_lines).strip())


def detect_kind(
    pdf_path: Path,
    config: DetectorConfig | None = None,
) -> PDFKind:
    """Classify PDF as text or scan using SAGE text-layer heuristics."""
    config = config or DetectorConfig()
    with fitz.open(pdf_path) as doc:
        if doc.page_count == 0:
            return "scan"
        lengths = [_content_len(page.get_text("text") or "", config) for page in doc]

    if not any(lengths):
        return "scan"

    median = statistics.median(lengths)
    mean = sum(lengths) / len(lengths)
    pages_above = sum(1 for length in lengths if length >= config.min_chars_per_page)
    fraction_above = pages_above / len(lengths)

    is_text = (
        median >= config.min_chars_per_page
        and mean >= config.min_chars_per_page
        and fraction_above >= config.min_text_page_ratio
    )
    return "text" if is_text else "scan"
