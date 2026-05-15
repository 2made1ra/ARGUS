from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

CATALOG_PAYLOAD_INDEXES: tuple[tuple[str, PayloadSchemaType], ...] = (
    ("price_item_id", PayloadSchemaType.UUID),
    ("import_batch_id", PayloadSchemaType.UUID),
    ("source_file_id", PayloadSchemaType.UUID),
    ("category", PayloadSchemaType.KEYWORD),
    ("category_normalized", PayloadSchemaType.KEYWORD),
    ("section", PayloadSchemaType.KEYWORD),
    ("section_normalized", PayloadSchemaType.KEYWORD),
    ("unit", PayloadSchemaType.KEYWORD),
    ("unit_price", PayloadSchemaType.FLOAT),
    ("has_vat", PayloadSchemaType.KEYWORD),
    ("vat_mode", PayloadSchemaType.KEYWORD),
    ("supplier_city", PayloadSchemaType.KEYWORD),
    ("supplier_city_normalized", PayloadSchemaType.KEYWORD),
    ("supplier_status", PayloadSchemaType.KEYWORD),
    ("supplier_status_normalized", PayloadSchemaType.KEYWORD),
    ("embedding_template_version", PayloadSchemaType.KEYWORD),
)


class QdrantSchemaMismatch(Exception):
    def __init__(
        self,
        collection: str,
        expected_dim: int,
        actual_dim: int | None,
    ) -> None:
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


async def bootstrap_catalog_collection(
    client: AsyncQdrantClient,
    name: str,
    dim: int,
) -> None:
    await bootstrap_collection(client, name, dim)
    for field_name, field_schema in CATALOG_PAYLOAD_INDEXES:
        await client.create_payload_index(
            collection_name=name,
            field_name=field_name,
            field_schema=field_schema,
        )


async def bootstrap_qdrant_collections(
    client: AsyncQdrantClient,
    *,
    document_collection: str,
    document_dim: int,
    catalog_collection: str,
    catalog_dim: int,
) -> None:
    await bootstrap_collection(client, document_collection, document_dim)
    await bootstrap_catalog_collection(client, catalog_collection, catalog_dim)


def _unnamed_dense_vector_size(vectors: object) -> int | None:
    if isinstance(vectors, VectorParams):
        return vectors.size

    return None


__all__ = [
    "CATALOG_PAYLOAD_INDEXES",
    "QdrantSchemaMismatch",
    "bootstrap_catalog_collection",
    "bootstrap_collection",
    "bootstrap_qdrant_collections",
]
