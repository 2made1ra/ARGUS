from sage.pdf.detector import DetectorConfig, detect_kind
from sage.pdf.ocr import ocr_pages
from sage.pdf.text_extractor import extract_text_pages

__all__ = [
    "detect_kind",
    "DetectorConfig",
    "extract_text_pages",
    "ocr_pages",
]
