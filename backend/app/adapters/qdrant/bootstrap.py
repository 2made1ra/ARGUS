from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams


class QdrantSchemaMismatch(Exception):
    def __init__(self, collection: str, expected_dim: int, actual_dim: int | None) -> None:
        super().__init__(
            f"Qdrant collection {collection!r} vector size mismatch: "
            f"expected {expected_dim}, got {actual_dim}",
        )
        self.collection = collection
        self.expected_dim = expected_dim
        self.actual_dim = actual_dim


async def bootstrap_collection(
    client: AsyncQdrantClient,
    name: str,
    dim: int,
) -> None:
    if not await client.collection_exists(collection_name=name):
        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        return

    collection_info = await client.get_collection(collection_name=name)
    if collection_info.config.params.sparse_vectors is not None:
        raise QdrantSchemaMismatch(name, dim, None)

    actual_dim = _unnamed_dense_vector_size(collection_info.config.params.vectors)
    if actual_dim != dim:
        raise QdrantSchemaMismatch(name, dim, actual_dim)


def _unnamed_dense_vector_size(vectors: object) -> int | None:
    if isinstance(vectors, VectorParams):
        return vectors.size

    return None


__all__ = ["QdrantSchemaMismatch", "bootstrap_collection"]
