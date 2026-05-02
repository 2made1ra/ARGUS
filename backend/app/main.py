from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.qdrant.bootstrap import bootstrap_collection
from app.adapters.qdrant.client import make_qdrant_client
from app.config import get_settings
from app.entrypoints.http.router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    qdrant = make_qdrant_client(settings.qdrant_url)
    try:
        await bootstrap_collection(
            qdrant,
            settings.qdrant_collection,
            settings.embedding_dim,
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
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

__all__ = ["app"]
