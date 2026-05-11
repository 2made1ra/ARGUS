from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.qdrant.bootstrap import bootstrap_qdrant_collections
from app.adapters.qdrant.client import make_qdrant_client
from app.config import get_settings
from app.entrypoints.http.router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    qdrant = make_qdrant_client(settings.qdrant_url)
    try:
        await bootstrap_qdrant_collections(
            qdrant,
            document_collection=settings.document_qdrant_collection,
            document_dim=settings.document_embedding_dim,
            catalog_collection=settings.catalog_qdrant_collection,
            catalog_dim=settings.catalog_embedding_dim,
        )
    finally:
        await qdrant.close()
    yield


app = FastAPI(
    title="ARGUS",
    description=(
        "Document intelligence platform for contractor management and contract search."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — dev only; no allow_credentials to avoid wildcard conflict
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

__all__ = ["app"]
