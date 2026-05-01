from collections.abc import Iterator

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

from app.core.domain.ids import DocumentId
from app.features.ingest.ports import VectorPoint

_UPSERT_BATCH_SIZE = 256


class QdrantVectorIndex:
    def __init__(self, client: AsyncQdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    async def upsert_chunks(self, points: list[VectorPoint]) -> None:
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

    async def delete_document(self, document_id: DocumentId) -> None:
        await self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    ),
                ],
            ),
        )


def _batches(points: list[VectorPoint], batch_size: int) -> Iterator[list[VectorPoint]]:
    for start in range(0, len(points), batch_size):
        yield points[start : start + batch_size]


__all__ = ["QdrantVectorIndex", "VectorPoint"]
