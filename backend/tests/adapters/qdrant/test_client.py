from qdrant_client import AsyncQdrantClient

from app.adapters.qdrant.client import make_qdrant_client


def test_make_qdrant_client_returns_async_client() -> None:
    client = make_qdrant_client("http://localhost:6333")

    assert isinstance(client, AsyncQdrantClient)
