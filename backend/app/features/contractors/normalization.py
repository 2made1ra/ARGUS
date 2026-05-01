from __future__ import annotations

import functools
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict, cast

import yaml  # type: ignore[import-untyped]

_YAML_PATH = Path(__file__).parent / "normalization_rules.yaml"
_EDGE_SEPARATOR_PATTERN = r"[\s«»\"'“”„.,;:!?()\[\]{}-]"


class NormalizationRules(TypedDict):
    legal_forms: list[str]
    stopwords: list[str]
    blocklist: list[str]


class NormalizationRulesError(Exception):
    pass


@functools.cache
def _load_rules() -> NormalizationRules:
    try:
        with _YAML_PATH.open(encoding="utf-8") as f:
            raw = cast(object, yaml.safe_load(f))
    except (OSError, yaml.YAMLError) as exc:
        raise NormalizationRulesError(
            "Failed to load contractor normalization rules"
        ) from exc

    if not isinstance(raw, Mapping):
        raise NormalizationRulesError(
            "Contractor normalization rules must be a mapping"
        )

    rules = cast(Mapping[str, object], raw)
    return NormalizationRules(
        legal_forms=_read_string_list(rules, "legal_forms"),
        stopwords=_read_string_list(rules, "stopwords"),
        blocklist=_read_string_list(rules, "blocklist"),
    )


def _read_string_list(rules: Mapping[str, object], key: str) -> list[str]:
    value = rules.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise NormalizationRulesError(
            f"Contractor normalization rule '{key}' must be a list of strings"
        )
    return cast(list[str], value)


def _strip_edge_legal_forms(value: str, legal_forms: list[str]) -> str:
    if not legal_forms:
        return value

    forms_pattern = "|".join(
        re.escape(form) for form in sorted(legal_forms, key=len, reverse=True)
    )
    leading = re.compile(
        rf"^(?:{_EDGE_SEPARATOR_PATTERN})*(?:{forms_pattern})\.?"
        rf"(?=$|{_EDGE_SEPARATOR_PATTERN})(?:{_EDGE_SEPARATOR_PATTERN})*",
        flags=re.IGNORECASE,
    )
    trailing = re.compile(
        rf"(?:{_EDGE_SEPARATOR_PATTERN})+(?:{forms_pattern})\.?"
        rf"(?:{_EDGE_SEPARATOR_PATTERN})*$",
        flags=re.IGNORECASE,
    )

    previous = None
    current = value
    while previous != current:
        previous = current
        current = leading.sub("", current)
        current = trailing.sub("", current)

    return current


def normalize_name(raw: str) -> str:
    s = raw.strip()

    rules = _load_rules()
    legal_forms = rules["legal_forms"]
    forms_upper = {form.upper() for form in legal_forms}
    s = _strip_edge_legal_forms(s, legal_forms)

    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)

    s = s.lower()

    s = " ".join(s.split())

    tokens = s.split()
    if (
        re.fullmatch(r"[а-яёa-z]+( [а-яёa-z]+){1,2}", s)
        and not any(token.upper() in forms_upper for token in tokens)
    ):
        s = " ".join(sorted(s.split()))

    return s


__all__ = ["NormalizationRulesError", "normalize_name"]
