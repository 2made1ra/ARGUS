from __future__ import annotations

from typing import Any


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


__all__ = ["optional_int"]
