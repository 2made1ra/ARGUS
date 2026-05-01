import re
from collections import Counter

from sage.models import Page

REPEATED_LINE_THRESHOLD = 0.60

_MOJIBAKE_REPLACEMENTS = {
    "â„–": "№",
    "â€“": "-",
    "â€”": "-",
    "â€˜": "'",
    "â€™": "'",
    "â€œ": '"',
    "â€ќ": '"',
    "Â«": "«",
    "Â»": "»",
    "Â": "",
}

_CP1251_UTF8_SPAN_RE = re.compile(r"[РС][А-Яа-яЁёA-Za-z0-9№.,;:!?\"'()/%\-\s]{1,}")
_LATIN1_UTF8_SPAN_RE = re.compile(r"[ÃÂÐÑ][\x80-\xffA-Za-z0-9№.,;:!?\"'()/%\-\s]{1,}")
_INLINE_WHITESPACE_RE = re.compile(r"[^\S\n]+")
_PAGE_MARKER_PATTERNS = [
    re.compile(r"(?im)^\s*-{0,3}\s*page\s+(\d+)(?:\s+of\s+(\d+))?\s*-{0,3}\s*$"),
    re.compile(r"(?im)^\s*страница\s+(\d+)(?:\s+из\s+(\d+))?\s*$"),
    re.compile(r"(?im)^\s*стр\.?\s*(\d+)(?:\s*/\s*(\d+))?\s*$"),
]


def normalize_pages(pages: list[Page]) -> list[Page]:
    cleaned_pages = [
        page.model_copy(update={"text": _clean_page_text(page.text)}) for page in pages
    ]
    repeated_lines = _find_repeated_lines(cleaned_pages)

    return [
        page.model_copy(
            update={
                "text": _normalize_page_markers(
                    _remove_lines(page.text, repeated_lines)
                )
            }
        )
        for page in cleaned_pages
    ]


def _clean_page_text(text: str) -> str:
    text = _remove_control_characters(text)
    text = _repair_mojibake(text)
    return _collapse_inline_whitespace(text)


def _remove_control_characters(text: str) -> str:
    return "".join(
        char
        for char in text
        if char == "\n" or char == "\t" or not _is_control_character(char)
    )


def _is_control_character(char: str) -> bool:
    return ord(char) < 32 or 127 <= ord(char) <= 159


def _repair_mojibake(text: str) -> str:
    text = _repair_full_text_mojibake(text)

    for broken, fixed in _MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(broken, fixed)

    text = _CP1251_UTF8_SPAN_RE.sub(_repair_cp1251_utf8_match, text)
    return _LATIN1_UTF8_SPAN_RE.sub(_repair_cp1252_or_latin1_utf8_match, text)


def _repair_full_text_mojibake(text: str) -> str:
    fixed = text
    for encoding in ("cp1251", "cp1252", "latin1"):
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if _looks_better(fixed, candidate):
            fixed = candidate
    return fixed


def _repair_cp1251_utf8_match(match: re.Match[str]) -> str:
    value = match.group(0)
    try:
        fixed = value.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return value
    return fixed if _looks_better(value, fixed) else value


def _repair_cp1252_or_latin1_utf8_match(match: re.Match[str]) -> str:
    value = match.group(0)
    fixed = value
    for encoding in ("cp1252", "latin1"):
        try:
            candidate = value.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if _looks_better(fixed, candidate):
            fixed = candidate
    return fixed


def _looks_better(original: str, fixed: str) -> bool:
    return _mojibake_score(fixed) < _mojibake_score(original)


def _mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in ("Р", "С", "Ð", "Ñ", "Ã", "Â", "â"))


def _collapse_inline_whitespace(text: str) -> str:
    return "\n".join(
        _INLINE_WHITESPACE_RE.sub(" ", line).strip()
        for line in text.split("\n")
    )


def _find_repeated_lines(pages: list[Page]) -> set[str]:
    if len(pages) < 2:
        return set()

    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({line for line in page.text.splitlines() if line})

    return {
        line
        for line, count in counts.items()
        if count / len(pages) > REPEATED_LINE_THRESHOLD
    }


def _remove_lines(text: str, lines_to_remove: set[str]) -> str:
    if not lines_to_remove:
        return text

    return "\n".join(
        line for line in text.splitlines() if line not in lines_to_remove
    ).strip()


def _normalize_page_markers(text: str) -> str:
    for pattern in _PAGE_MARKER_PATTERNS:
        text = pattern.sub(_format_page_marker, text)
    return text


def _format_page_marker(match: re.Match[str]) -> str:
    page_number = match.group(1)
    page_total = match.group(2)
    if page_total:
        return f"[PAGE {page_number} OF {page_total}]"
    return f"[PAGE {page_number}]"
