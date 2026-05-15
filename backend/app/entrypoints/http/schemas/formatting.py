from __future__ import annotations

from decimal import Decimal


def decimal_string(value: Decimal) -> str:
    return f"{value:.2f}"


__all__ = ["decimal_string"]
