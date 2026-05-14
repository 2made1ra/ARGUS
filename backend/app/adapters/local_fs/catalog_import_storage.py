from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

_CHUNK_SIZE = 1024 * 1024
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class LocalCatalogImportStorage:
    def __init__(self, base: Path) -> None:
        base.mkdir(parents=True, exist_ok=True)
        self._base = base.resolve()

    async def save(
        self,
        job_id: UUID,
        stream: BinaryIO,
        filename: str,
    ) -> tuple[Path, int]:
        safe_filename = _sanitize_filename(filename)
        destination = (self._base / f"{job_id}-{safe_filename}").resolve()
        if destination.parent != self._base:
            raise ValueError("Invalid catalog import destination path")
        size = await asyncio.to_thread(_write_stream, stream, destination)
        return destination, size


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "prices.csv"
    sanitized = _SAFE_FILENAME_RE.sub("_", name).strip("._")
    return sanitized or "prices.csv"


def _write_stream(stream: BinaryIO, destination: Path) -> int:
    size = 0
    with destination.open("wb") as output:
        while chunk := stream.read(_CHUNK_SIZE):
            size += len(chunk)
            output.write(chunk)
    return size


__all__ = ["LocalCatalogImportStorage"]
