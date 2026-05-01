from qdrant_client import AsyncQdrantClient


def make_qdrant_client(url: str) -> AsyncQdrantClient:
    return AsyncQdrantClient(url=url, trust_env=False)


__all__ = ["make_qdrant_client"]
