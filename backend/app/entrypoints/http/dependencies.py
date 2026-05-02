from pathlib import Path

from fastapi import Depends
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.celery.task_queue import CeleryIngestionTaskQueue
from app.adapters.llm.embeddings import LMStudioEmbeddings
from app.adapters.local_fs.file_storage import LocalFileStorage
from app.adapters.qdrant.search import QdrantVectorSearch
from app.adapters.sqlalchemy.contractors import (
    SqlAlchemyContractorRepository,
    SqlAlchemyRawContractorMappingRepository,
)
from app.adapters.sqlalchemy.documents import SqlAlchemyDocumentRepository
from app.adapters.sqlalchemy.fields import SqlAlchemyFieldsRepository
from app.adapters.sqlalchemy.summaries import SqlAlchemySummaryRepository
from app.adapters.sqlalchemy.unit_of_work import SessionUnitOfWork
from app.config import Settings, get_settings
from app.entrypoints.http.session import _session, get_qdrant_client, get_sessionmaker
from app.features.contractors.use_cases.get_contractor_profile import (
    GetContractorProfileUseCase,
)
from app.features.contractors.use_cases.list_contractor_documents import (
    ListContractorDocumentsUseCase,
)
from app.features.documents.use_cases.get_document import GetDocumentUseCase
from app.features.documents.use_cases.get_document_facts import GetDocumentFactsUseCase
from app.features.documents.use_cases.list_documents import ListDocumentsUseCase
from app.features.documents.use_cases.update_document_facts import UpdateDocumentFactsUseCase
from app.features.ingest.use_cases.upload_document import UploadDocumentUseCase
from app.features.search.use_cases.search_contractors import SearchContractorsUseCase
from app.features.search.use_cases.search_documents import SearchDocumentsUseCase
from app.features.search.use_cases.search_within_document import (
    SearchWithinDocumentUseCase,
)

# ---------------------------------------------------------------------------
# Ingest use cases
# ---------------------------------------------------------------------------


def get_upload_uc(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(_session),
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(
        storage=LocalFileStorage(Path(settings.upload_dir)),
        documents=SqlAlchemyDocumentRepository(session),
        tasks=CeleryIngestionTaskQueue(),
        uow=SessionUnitOfWork(session),
    )


# ---------------------------------------------------------------------------
# Documents use cases
# ---------------------------------------------------------------------------


def get_get_document_uc(
    session: AsyncSession = Depends(_session),
) -> GetDocumentUseCase:
    return GetDocumentUseCase(documents=SqlAlchemyDocumentRepository(session))


def get_list_documents_uc(
    session: AsyncSession = Depends(_session),
) -> ListDocumentsUseCase:
    return ListDocumentsUseCase(documents=SqlAlchemyDocumentRepository(session))


def get_document_facts_uc(
    session: AsyncSession = Depends(_session),
) -> GetDocumentFactsUseCase:
    return GetDocumentFactsUseCase(
        documents=SqlAlchemyDocumentRepository(session),
        fields=SqlAlchemyFieldsRepository(session),
        summaries=SqlAlchemySummaryRepository(session),
    )


def get_update_document_facts_uc(
    session: AsyncSession = Depends(_session),
) -> UpdateDocumentFactsUseCase:
    return UpdateDocumentFactsUseCase(
        fields=SqlAlchemyFieldsRepository(session),
        summaries=SqlAlchemySummaryRepository(session),
        uow=SessionUnitOfWork(session),
    )


def get_search_within_uc(
    settings: Settings = Depends(get_settings),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> SearchWithinDocumentUseCase:
    return SearchWithinDocumentUseCase(
        embeddings=LMStudioEmbeddings(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_embedding_model,
            embedding_dim=settings.embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.qdrant_collection),
    )


# ---------------------------------------------------------------------------
# Contractors use cases
# ---------------------------------------------------------------------------


def get_contractor_profile_uc(
    session: AsyncSession = Depends(_session),
) -> GetContractorProfileUseCase:
    return GetContractorProfileUseCase(
        contractors=SqlAlchemyContractorRepository(session),
        mappings=SqlAlchemyRawContractorMappingRepository(session),
    )


def get_list_contractor_documents_uc(
    session: AsyncSession = Depends(_session),
) -> ListContractorDocumentsUseCase:
    return ListContractorDocumentsUseCase(
        contractors=SqlAlchemyContractorRepository(session),
    )


def get_search_documents_uc(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(_session),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> SearchDocumentsUseCase:
    return SearchDocumentsUseCase(
        embeddings=LMStudioEmbeddings(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_embedding_model,
            embedding_dim=settings.embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.qdrant_collection),
        documents=SqlAlchemyDocumentRepository(session),
    )


# ---------------------------------------------------------------------------
# Search use cases
# ---------------------------------------------------------------------------


def get_search_contractors_uc(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(_session),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> SearchContractorsUseCase:
    return SearchContractorsUseCase(
        embeddings=LMStudioEmbeddings(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_embedding_model,
            embedding_dim=settings.embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.qdrant_collection),
        contractors=SqlAlchemyContractorRepository(session),
    )


__all__ = [
    "get_contractor_profile_uc",
    "get_document_facts_uc",
    "get_get_document_uc",
    "get_list_contractor_documents_uc",
    "get_list_documents_uc",
    "get_qdrant_client",
    "get_search_contractors_uc",
    "get_search_documents_uc",
    "get_search_within_uc",
    "get_sessionmaker",
    "get_update_document_facts_uc",
    "get_upload_uc",
]
