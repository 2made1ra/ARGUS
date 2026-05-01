from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Any

import yaml

_YAML_PATH = Path(__file__).parent / "normalization_rules.yaml"


@functools.lru_cache(maxsize=None)
def _load_rules() -> dict[str, Any]:
    with _YAML_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]


def normalize_name(raw: str) -> str:
    s = raw.strip()

    rules = _load_rules()
    forms_upper = {f.upper() for f in rules.get("legal_forms", [])}
    tokens = re.split(r'[\s«»"\']+', s)
    s = " ".join(t for t in tokens if t.upper() not in forms_upper)

    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)

    s = s.lower()

    s = " ".join(s.split())

    if re.fullmatch(r"[а-яёa-z]+( [а-яёa-z]+){1,2}", s):
        s = " ".join(sorted(s.split()))

    return s


__all__ = ["normalize_name"]
