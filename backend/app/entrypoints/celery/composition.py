import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapters.llm.embeddings import LMStudioEmbeddings
from app.adapters.qdrant.catalog_index import QdrantCatalogIndex
from app.adapters.qdrant.client import make_qdrant_client
from app.adapters.qdrant.index import QdrantVectorIndex
from app.adapters.sage.processor import SageProcessorAdapter
from app.adapters.sqlalchemy.catalog_import_jobs import (
    SqlAlchemyCatalogImportJobRepository,
)
from app.adapters.sqlalchemy.chunks import SqlAlchemyChunkRepository
from app.adapters.sqlalchemy.contractors import (
    SqlAlchemyContractorRepository,
    SqlAlchemyRawContractorMappingRepository,
)
from app.adapters.sqlalchemy.documents import SqlAlchemyDocumentRepository
from app.adapters.sqlalchemy.fields import SqlAlchemyFieldsRepository
from app.adapters.sqlalchemy.price_imports import SqlAlchemyPriceImportRepository
from app.adapters.sqlalchemy.price_items import SqlAlchemyPriceItemRepository
from app.adapters.sqlalchemy.session import make_engine, make_sessionmaker
from app.adapters.sqlalchemy.summaries import SqlAlchemySummaryRepository
from app.adapters.sqlalchemy.unit_of_work import SessionUnitOfWork
from app.config import get_settings
from app.core.ports.unit_of_work import UnitOfWork
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase
from app.features.catalog.use_cases.index_price_items import IndexPriceItemsUseCase
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


def build_import_prices_csv_uc() -> ImportPricesCsvUseCase:
    settings = get_settings()
    session = _session()
    return ImportPricesCsvUseCase(
        imports=SqlAlchemyPriceImportRepository(session),
        items=SqlAlchemyPriceItemRepository(session),
        uow=SessionUnitOfWork(session),
        embedding_model=settings.catalog_embedding_model,
    )


@asynccontextmanager
async def build_catalog_index_uc() -> AsyncIterator[IndexPriceItemsUseCase]:
    settings = get_settings()
    session = _session()
    qdrant_client = make_qdrant_client(settings.qdrant_url)
    try:
        yield IndexPriceItemsUseCase(
            items=SqlAlchemyPriceItemRepository(session),
            embeddings=LMStudioEmbeddings(
                base_url=settings.lm_studio_url,
                model=settings.catalog_embedding_model,
                embedding_dim=settings.catalog_embedding_dim,
            ),
            index=QdrantCatalogIndex(qdrant_client, settings.catalog_qdrant_collection),
            uow=SessionUnitOfWork(session),
            catalog_embedding_model=settings.catalog_embedding_model,
            catalog_embedding_dim=settings.catalog_embedding_dim,
            catalog_embedding_template_version=(
                settings.catalog_embedding_template_version
            ),
            catalog_document_prefix=settings.catalog_document_prefix,
        )
    finally:
        await qdrant_client.close()


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
                embedding_dim=settings.document_embedding_dim,
            ),
            index=QdrantVectorIndex(
                qdrant_client,
                settings.document_qdrant_collection,
            ),
            uow=SessionUnitOfWork(session),
        )
    finally:
        await qdrant_client.close()


def build_document_repository() -> tuple[SqlAlchemyDocumentRepository, UnitOfWork]:
    session = _session()
    return SqlAlchemyDocumentRepository(session), SessionUnitOfWork(session)


def build_catalog_import_job_repository() -> tuple[
    SqlAlchemyCatalogImportJobRepository,
    UnitOfWork,
]:
    session = _session()
    return SqlAlchemyCatalogImportJobRepository(session), SessionUnitOfWork(session)


__all__ = [
    "build_catalog_import_job_repository",
    "build_catalog_index_uc",
    "build_document_repository",
    "build_import_prices_csv_uc",
    "build_index_uc",
    "build_process_uc",
    "build_resolve_uc",
]
