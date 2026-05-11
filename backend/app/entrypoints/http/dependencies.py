from pathlib import Path
from typing import Annotated

from fastapi import Depends
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.celery.task_queue import CeleryIngestionTaskQueue
from app.adapters.llm.chat import LMStudioChatClient
from app.adapters.llm.embeddings import LMStudioEmbeddings
from app.adapters.local_fs.file_storage import LocalFileStorage
from app.adapters.qdrant.index import QdrantVectorIndex
from app.adapters.qdrant.search import QdrantVectorSearch
from app.adapters.sqlalchemy.contractors import (
    SqlAlchemyContractorRepository,
    SqlAlchemyRawContractorMappingRepository,
)
from app.adapters.sqlalchemy.documents import SqlAlchemyDocumentRepository
from app.adapters.sqlalchemy.fields import SqlAlchemyFieldsRepository
from app.adapters.sqlalchemy.price_imports import SqlAlchemyPriceImportRepository
from app.adapters.sqlalchemy.price_items import SqlAlchemyPriceItemRepository
from app.adapters.sqlalchemy.summaries import SqlAlchemySummaryRepository
from app.adapters.sqlalchemy.unit_of_work import SessionUnitOfWork
from app.config import Settings, get_settings
from app.entrypoints.http.session import _session, get_qdrant_client, get_sessionmaker
from app.features.catalog.use_cases.get_price_item import GetPriceItemUseCase
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase
from app.features.catalog.use_cases.list_price_items import ListPriceItemsUseCase
from app.features.contractors.use_cases.get_contractor_profile import (
    GetContractorProfileUseCase,
)
from app.features.contractors.use_cases.list_contractor_documents import (
    ListContractorDocumentsUseCase,
)
from app.features.contractors.use_cases.list_contractors import ListContractorsUseCase
from app.features.documents.use_cases.delete_document import DeleteDocumentUseCase
from app.features.documents.use_cases.get_document import GetDocumentUseCase
from app.features.documents.use_cases.get_document_facts import GetDocumentFactsUseCase
from app.features.documents.use_cases.get_document_preview import (
    GetDocumentPreviewUseCase,
)
from app.features.documents.use_cases.list_documents import ListDocumentsUseCase
from app.features.documents.use_cases.update_document_facts import (
    UpdateDocumentFactsUseCase,
)
from app.features.ingest.use_cases.upload_document import UploadDocumentUseCase
from app.features.search.use_cases.answer_contractor import AnswerContractorUseCase
from app.features.search.use_cases.answer_document import AnswerDocumentUseCase
from app.features.search.use_cases.answer_global import AnswerGlobalSearchUseCase
from app.features.search.use_cases.search_contractors import SearchContractorsUseCase
from app.features.search.use_cases.search_documents import SearchDocumentsUseCase
from app.features.search.use_cases.search_within_document import (
    SearchWithinDocumentUseCase,
)

# ---------------------------------------------------------------------------
# Catalog use cases
# ---------------------------------------------------------------------------


def get_import_prices_csv_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
) -> ImportPricesCsvUseCase:
    return ImportPricesCsvUseCase(
        imports=SqlAlchemyPriceImportRepository(session),
        items=SqlAlchemyPriceItemRepository(session),
        uow=SessionUnitOfWork(session),
        embedding_model=settings.lm_studio_embedding_model,
    )


def get_list_price_items_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> ListPriceItemsUseCase:
    return ListPriceItemsUseCase(items=SqlAlchemyPriceItemRepository(session))


def get_get_price_item_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> GetPriceItemUseCase:
    return GetPriceItemUseCase(items=SqlAlchemyPriceItemRepository(session))


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


def get_document_preview_uc(
    session: AsyncSession = Depends(_session),
) -> GetDocumentPreviewUseCase:
    return GetDocumentPreviewUseCase(documents=SqlAlchemyDocumentRepository(session))


def get_update_document_facts_uc(
    session: AsyncSession = Depends(_session),
) -> UpdateDocumentFactsUseCase:
    return UpdateDocumentFactsUseCase(
        fields=SqlAlchemyFieldsRepository(session),
        summaries=SqlAlchemySummaryRepository(session),
        uow=SessionUnitOfWork(session),
    )


def get_delete_document_uc(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(_session),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(
        documents=SqlAlchemyDocumentRepository(session),
        vectors=QdrantVectorIndex(qdrant, settings.qdrant_collection),
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


def get_list_contractors_uc(
    session: AsyncSession = Depends(_session),
) -> ListContractorsUseCase:
    return ListContractorsUseCase(
        contractors=SqlAlchemyContractorRepository(session),
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


def get_global_rag_answer_uc(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(_session),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> AnswerGlobalSearchUseCase:
    return AnswerGlobalSearchUseCase(
        embeddings=LMStudioEmbeddings(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_embedding_model,
            embedding_dim=settings.embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.qdrant_collection),
        contractors=SqlAlchemyContractorRepository(session),
        documents=SqlAlchemyDocumentRepository(session),
        llm=LMStudioChatClient(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_llm_model,
        ),
        similarity_top_k=settings.rag_similarity_top_k,
        context_top_k=settings.rag_context_top_k,
    )


def get_contractor_rag_answer_uc(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(_session),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> AnswerContractorUseCase:
    return AnswerContractorUseCase(
        embeddings=LMStudioEmbeddings(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_embedding_model,
            embedding_dim=settings.embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.qdrant_collection),
        contractors=SqlAlchemyContractorRepository(session),
        documents=SqlAlchemyDocumentRepository(session),
        llm=LMStudioChatClient(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_llm_model,
        ),
        similarity_top_k=settings.rag_similarity_top_k,
        context_top_k=settings.rag_context_top_k,
    )


def get_document_rag_answer_uc(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(_session),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> AnswerDocumentUseCase:
    return AnswerDocumentUseCase(
        embeddings=LMStudioEmbeddings(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_embedding_model,
            embedding_dim=settings.embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.qdrant_collection),
        documents=SqlAlchemyDocumentRepository(session),
        fields=SqlAlchemyFieldsRepository(session),
        summaries=SqlAlchemySummaryRepository(session),
        llm=LMStudioChatClient(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_llm_model,
        ),
        similarity_top_k=settings.rag_similarity_top_k,
        context_top_k=settings.rag_context_top_k,
    )


__all__ = [
    "get_contractor_profile_uc",
    "get_contractor_rag_answer_uc",
    "get_delete_document_uc",
    "get_document_facts_uc",
    "get_document_preview_uc",
    "get_document_rag_answer_uc",
    "get_get_price_item_uc",
    "get_get_document_uc",
    "get_global_rag_answer_uc",
    "get_import_prices_csv_uc",
    "get_list_contractors_uc",
    "get_list_contractor_documents_uc",
    "get_list_documents_uc",
    "get_list_price_items_uc",
    "get_qdrant_client",
    "get_search_contractors_uc",
    "get_search_documents_uc",
    "get_search_within_uc",
    "get_sessionmaker",
    "get_update_document_facts_uc",
    "get_upload_uc",
]
