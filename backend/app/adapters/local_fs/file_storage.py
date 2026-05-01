import asyncio
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

_CHUNK_SIZE = 1024 * 1024


class LocalFileStorage:
    def __init__(self, base: Path) -> None:
        base.mkdir(parents=True, exist_ok=True)
        self._base = base.resolve()

    async def save(self, stream: BinaryIO, filename: str) -> Path:
        destination = self._base / f"{uuid4()}__{filename}"
        await asyncio.to_thread(_write_stream, stream, destination)
        return destination.resolve()


def _write_stream(stream: BinaryIO, destination: Path) -> None:
    with destination.open("wb") as output:
        while chunk := stream.read(_CHUNK_SIZE):
            output.write(chunk)


__all__ = ["LocalFileStorage"]
