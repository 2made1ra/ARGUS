import re
from collections import Counter
from dataclasses import dataclass
from importlib.resources import files

from sage.models import Page

_RULES_FILE = "normalization_rules.yaml"


@dataclass(frozen=True)
class NormalizationRules:
    edo_noise_patterns: tuple[str, ...] = ()
    repeating_footer_threshold: float = 0.60
    whitespace_collapse: bool = True
    fix_mojibake: bool = True


_NORMALIZATION_RULES: NormalizationRules | None = None

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
    rules = _get_normalization_rules()
    cleaned_pages = [
        page.model_copy(
            update={
                "text": _remove_edo_noise_lines(
                    _clean_page_text(page.text, rules), rules
                )
            }
        )
        for page in pages
    ]
    repeated_lines = _find_repeated_lines(cleaned_pages, rules)

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


def _clean_page_text(text: str, rules: NormalizationRules) -> str:
    text = _remove_control_characters(text)
    if rules.fix_mojibake:
        text = _repair_mojibake(text)
    if rules.whitespace_collapse:
        text = _collapse_inline_whitespace(text)
    return text


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
        _INLINE_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")
    )


def _find_repeated_lines(
    pages: list[Page],
    rules: NormalizationRules,
) -> set[str]:
    if len(pages) < 2:
        return set()

    counts: Counter[str] = Counter()
    for page in pages:
        counts.update(
            {
                line
                for line in page.text.splitlines()
                if line and not _is_edo_noise_line(line, rules)
            }
        )

    return {
        line
        for line, count in counts.items()
        if count / len(pages) > rules.repeating_footer_threshold
    }


def _remove_lines(text: str, lines_to_remove: set[str]) -> str:
    if not lines_to_remove:
        return text

    return "\n".join(
        line for line in text.splitlines() if line not in lines_to_remove
    ).strip()


def _remove_edo_noise_lines(text: str, rules: NormalizationRules) -> str:
    if not rules.edo_noise_patterns:
        return text

    return "\n".join(
        line for line in text.splitlines() if not _is_edo_noise_line(line, rules)
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


def _is_edo_noise_line(line: str, rules: NormalizationRules) -> bool:
    normalized = line.casefold()
    return any(pattern.casefold() in normalized for pattern in rules.edo_noise_patterns)


def _get_normalization_rules() -> NormalizationRules:
    global _NORMALIZATION_RULES
    if _NORMALIZATION_RULES is None:
        _NORMALIZATION_RULES = _load_normalization_rules()
    return _NORMALIZATION_RULES


def _load_normalization_rules() -> NormalizationRules:
    content = (files("sage.normalizer") / _RULES_FILE).read_text(encoding="utf-8")
    data = _parse_simple_yaml(content)
    patterns = data.get("edo_noise_patterns", ())
    if not isinstance(patterns, tuple):
        patterns = ()
    return NormalizationRules(
        edo_noise_patterns=patterns,
        repeating_footer_threshold=_as_float(
            data.get("repeating_footer_threshold"),
            0.60,
        ),
        whitespace_collapse=bool(data.get("whitespace_collapse", True)),
        fix_mojibake=bool(data.get("fix_mojibake", True)),
    )


def _parse_simple_yaml(content: str) -> dict[str, object]:
    data: dict[str, object] = {}
    current_list_key: str | None = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- ") and current_list_key is not None:
            current = data[current_list_key]
            if isinstance(current, tuple):
                data[current_list_key] = (*current, _unquote_yaml_value(line[2:]))
            continue
        if ":" not in line:
            continue

        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if value:
            data[key] = _parse_yaml_scalar(value)
            current_list_key = None
        else:
            data[key] = ()
            current_list_key = key

    return data


def _parse_yaml_scalar(value: str) -> object:
    normalized = value.casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return _unquote_yaml_value(value)


def _unquote_yaml_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _as_float(value: object, default: float) -> float:
    if isinstance(value, int | float | str):
        return float(value)
    return default
