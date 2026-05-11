from __future__ import annotations

from collections.abc import Iterator

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

from app.features.catalog.ports import CatalogVectorPoint

_UPSERT_BATCH_SIZE = 256


class QdrantCatalogIndex:
    def __init__(self, client: AsyncQdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    async def upsert_points(self, points: list[CatalogVectorPoint]) -> None:
        for batch in _batches(points, _UPSERT_BATCH_SIZE):
            await self._client.upsert(
                collection_name=self._collection,
                points=[
                    PointStruct(
                        id=point.id,
                        vector=point.vector,
                        payload=point.payload,
                    )
                    for point in batch
                ],
            )


def _batches(
    points: list[CatalogVectorPoint],
    batch_size: int,
) -> Iterator[list[CatalogVectorPoint]]:
    for start in range(0, len(points), batch_size):
        yield points[start : start + batch_size]


__all__ = ["QdrantCatalogIndex"]
