import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapters.llm.embeddings import LMStudioEmbeddings
from app.adapters.qdrant.client import make_qdrant_client
from app.adapters.qdrant.index import QdrantVectorIndex
from app.adapters.sage.processor import SageProcessorAdapter
from app.adapters.sqlalchemy.chunks import SqlAlchemyChunkRepository
from app.adapters.sqlalchemy.contractors import (
    SqlAlchemyContractorRepository,
    SqlAlchemyRawContractorMappingRepository,
)
from app.adapters.sqlalchemy.documents import SqlAlchemyDocumentRepository
from app.adapters.sqlalchemy.fields import SqlAlchemyFieldsRepository
from app.adapters.sqlalchemy.session import make_engine, make_sessionmaker
from app.adapters.sqlalchemy.summaries import SqlAlchemySummaryRepository
from app.adapters.sqlalchemy.unit_of_work import SessionUnitOfWork
from app.config import get_settings
from app.core.ports.unit_of_work import UnitOfWork
from app.features.contractors.use_cases.resolve_contractor import (
    ResolveContractorUseCase,
)
from app.features.ingest.use_cases.index_document import IndexDocumentUseCase
from app.features.ingest.use_cases.process_document import ProcessDocumentUseCase


@lru_cache
def _engine() -> AsyncEngine:
    return make_engine(get_settings().database_url)


@lru_cache
def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return make_sessionmaker(_engine())


def _session() -> AsyncSession:
    return _sessionmaker()()


def build_process_uc() -> ProcessDocumentUseCase:
    settings = get_settings()
    session = _session()
    os.environ.setdefault("LM_STUDIO_URL", settings.lm_studio_url)
    os.environ.setdefault("LM_STUDIO_LLM_MODEL", settings.lm_studio_llm_model)
    return ProcessDocumentUseCase(
        documents=SqlAlchemyDocumentRepository(session),
        chunks=SqlAlchemyChunkRepository(session),
        fields=SqlAlchemyFieldsRepository(session),
        summaries=SqlAlchemySummaryRepository(session),
        sage=SageProcessorAdapter(
            work_dir=Path(settings.upload_dir) / "work",
        ),
        uow=SessionUnitOfWork(session),
    )


def build_resolve_uc() -> ResolveContractorUseCase:
    session = _session()
    return ResolveContractorUseCase(
        contractors=SqlAlchemyContractorRepository(session),
        mappings=SqlAlchemyRawContractorMappingRepository(session),
        documents=SqlAlchemyDocumentRepository(session),
        fields=SqlAlchemyFieldsRepository(session),
        uow=SessionUnitOfWork(session),
    )


@asynccontextmanager
async def build_index_uc() -> AsyncIterator[IndexDocumentUseCase]:
    settings = get_settings()
    session = _session()
    qdrant_client = make_qdrant_client(settings.qdrant_url)
    try:
        yield IndexDocumentUseCase(
            documents=SqlAlchemyDocumentRepository(session),
            chunks=SqlAlchemyChunkRepository(session),
            fields=SqlAlchemyFieldsRepository(session),
            summaries=SqlAlchemySummaryRepository(session),
            contractors=SqlAlchemyContractorRepository(session),
            embeddings=LMStudioEmbeddings(
                base_url=settings.lm_studio_url,
                model=settings.lm_studio_embedding_model,
                embedding_dim=settings.embedding_dim,
            ),
            index=QdrantVectorIndex(qdrant_client, settings.qdrant_collection),
            uow=SessionUnitOfWork(session),
        )
    finally:
        await qdrant_client.close()


def build_document_repository() -> tuple[SqlAlchemyDocumentRepository, UnitOfWork]:
    session = _session()
    return SqlAlchemyDocumentRepository(session), SessionUnitOfWork(session)


__all__ = [
    "build_document_repository",
    "build_index_uc",
    "build_process_uc",
    "build_resolve_uc",
]
