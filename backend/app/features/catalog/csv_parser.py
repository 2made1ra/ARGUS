from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass


@dataclass(slots=True)
class ParsedPriceCsvRow:
    row_number: int
    raw: dict[str, str]
    legacy_embedding_present: bool
    legacy_embedding_dim: int | None


def parse_price_csv(content: bytes | str) -> list[ParsedPriceCsvRow]:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.DictReader(io.StringIO(text))
    rows: list[ParsedPriceCsvRow] = []

    for row_number, row in enumerate(reader, start=2):
        raw = {
            key: "" if value is None else value
            for key, value in row.items()
            if key is not None
        }
        embedding = raw.get("embedding", "")
        present = bool(embedding.strip())
        rows.append(
            ParsedPriceCsvRow(
                row_number=row_number,
                raw=raw,
                legacy_embedding_present=present,
                legacy_embedding_dim=(
                    _legacy_embedding_dim(embedding) if present else None
                ),
            ),
        )
    return rows


def _legacy_embedding_dim(value: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, list):
        return None
    return len(parsed)


__all__ = ["ParsedPriceCsvRow", "parse_price_csv"]
