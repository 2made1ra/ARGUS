from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.assistant.catalog_tools import (
    CatalogItemDetailsToolAdapter,
    CatalogSearchToolAdapter,
)
from app.adapters.celery.catalog_task_queue import CeleryCatalogImportTaskQueue
from app.adapters.celery.task_queue import CeleryIngestionTaskQueue
from app.adapters.llm.assistant_agent_planner import LangChainAssistantAgentPlanner
from app.adapters.llm.chat import LangChainChatClient
from app.adapters.llm.embeddings import LMStudioEmbeddings
from app.adapters.local_fs.catalog_import_storage import LocalCatalogImportStorage
from app.adapters.local_fs.file_storage import LocalFileStorage
from app.adapters.qdrant.catalog_index import QdrantCatalogIndex
from app.adapters.qdrant.catalog_search import QdrantCatalogSearch
from app.adapters.qdrant.client import make_qdrant_client
from app.adapters.qdrant.index import QdrantVectorIndex
from app.adapters.qdrant.search import QdrantVectorSearch
from app.adapters.sqlalchemy.catalog_import_jobs import (
    SqlAlchemyCatalogImportJobRepository,
)
from app.adapters.sqlalchemy.contractors import (
    SqlAlchemyContractorRepository,
    SqlAlchemyRawContractorMappingRepository,
)
from app.adapters.sqlalchemy.documents import SqlAlchemyDocumentRepository
from app.adapters.sqlalchemy.fields import SqlAlchemyFieldsRepository
from app.adapters.sqlalchemy.price_imports import SqlAlchemyPriceImportRepository
from app.adapters.sqlalchemy.price_items import SqlAlchemyPriceItemRepository
from app.adapters.sqlalchemy.summaries import SqlAlchemySummaryRepository
from app.adapters.sqlalchemy.unit_of_work import SessionUnitOfWork, SqlAlchemyUnitOfWork
from app.adapters.supplier_verification.manual import (
    ManualNotVerifiedSupplierVerificationAdapter,
)
from app.config import Settings, get_settings
from app.entrypoints.http.session import _session, get_qdrant_client, get_sessionmaker
from app.features.assistant.agent_graph import (
    AssistantGraphRunner,
    DemoAssistantAgentPlanner,
)
from app.features.catalog.entities.import_job import CatalogImportJob
from app.features.catalog.ports import (
    CatalogSearchFilters as CatalogVectorFilters,
)
from app.features.catalog.ports import CatalogSearchHit
from app.features.catalog.use_cases.get_import_job import GetCatalogImportJobUseCase
from app.features.catalog.use_cases.get_price_item import GetPriceItemUseCase
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase
from app.features.catalog.use_cases.index_price_items import IndexPriceItemsUseCase
from app.features.catalog.use_cases.list_price_items import ListPriceItemsUseCase
from app.features.catalog.use_cases.search_price_items import SearchPriceItemsUseCase
from app.features.catalog.use_cases.start_import_job import StartCatalogImportJobUseCase
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

type CatalogImportJobFetcher = Callable[[UUID], Coroutine[Any, Any, CatalogImportJob]]


def get_import_prices_csv_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
) -> ImportPricesCsvUseCase:
    return ImportPricesCsvUseCase(
        imports=SqlAlchemyPriceImportRepository(session),
        items=SqlAlchemyPriceItemRepository(session),
        uow=SessionUnitOfWork(session),
        embedding_model=settings.catalog_embedding_model,
    )


def get_start_catalog_import_job_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
) -> StartCatalogImportJobUseCase:
    return StartCatalogImportJobUseCase(
        storage=LocalCatalogImportStorage(
            Path(settings.upload_dir) / "catalog_imports",
        ),
        jobs=SqlAlchemyCatalogImportJobRepository(session),
        tasks=CeleryCatalogImportTaskQueue(),
        uow=SessionUnitOfWork(session),
    )


def get_get_catalog_import_job_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> GetCatalogImportJobUseCase:
    return GetCatalogImportJobUseCase(
        jobs=SqlAlchemyCatalogImportJobRepository(session),
    )


def get_catalog_import_job_fetcher(
    sm: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_sessionmaker),
    ],
) -> CatalogImportJobFetcher:
    async def _fetch(job_id: UUID) -> CatalogImportJob:
        async with SqlAlchemyUnitOfWork(sm) as uow:
            return await SqlAlchemyCatalogImportJobRepository(uow.session).get(job_id)

    return _fetch


def get_list_price_items_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> ListPriceItemsUseCase:
    return ListPriceItemsUseCase(items=SqlAlchemyPriceItemRepository(session))


def get_get_price_item_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> GetPriceItemUseCase:
    return GetPriceItemUseCase(items=SqlAlchemyPriceItemRepository(session))


def get_index_price_items_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> IndexPriceItemsUseCase:
    return IndexPriceItemsUseCase(
        items=SqlAlchemyPriceItemRepository(session),
        index=QdrantCatalogIndex(qdrant, settings.catalog_qdrant_collection),
        uow=SessionUnitOfWork(session),
        catalog_embedding_model=settings.catalog_embedding_model,
        catalog_embedding_dim=settings.catalog_embedding_dim,
        catalog_embedding_template_version=settings.catalog_embedding_template_version,
    )


class _DisabledCatalogEmbeddings:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Catalog semantic search is disabled")


class _DisabledCatalogVectorSearch:
    async def search(
        self,
        *,
        query_vector: list[float],
        filters: CatalogVectorFilters | None,
        limit: int,
    ) -> list[CatalogSearchHit]:
        raise RuntimeError("Catalog semantic search is disabled")


def _catalog_embeddings(settings: Settings) -> LMStudioEmbeddings:
    return LMStudioEmbeddings(
        base_url=settings.lm_studio_url,
        model=settings.catalog_embedding_model,
        api_key=settings.api_key,
        embedding_dim=settings.catalog_embedding_dim,
    )


def _document_embeddings(settings: Settings) -> LMStudioEmbeddings:
    return LMStudioEmbeddings(
        base_url=settings.lm_studio_url,
        model=settings.lm_studio_embedding_model,
        api_key=settings.api_key,
        embedding_dim=settings.document_embedding_dim,
    )


def _rag_llm(settings: Settings) -> LangChainChatClient:
    return LangChainChatClient(
        base_url=settings.lm_studio_url,
        model=settings.lm_studio_llm_model,
        api_key=settings.api_key or "not-needed",
        timeout=settings.rag_answer_timeout_seconds,
    )


async def get_search_price_items_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
) -> AsyncIterator[SearchPriceItemsUseCase]:
    if settings.argus_demo_mode:
        yield SearchPriceItemsUseCase(
            items=SqlAlchemyPriceItemRepository(session),
            embeddings=_DisabledCatalogEmbeddings(),
            vector_search=_DisabledCatalogVectorSearch(),
            catalog_query_prefix=settings.catalog_query_prefix,
            catalog_embedding_template_version=(
                settings.catalog_embedding_template_version
            ),
            semantic_search_enabled=False,
        )
        return

    qdrant = make_qdrant_client(settings.qdrant_url)
    try:
        yield SearchPriceItemsUseCase(
            items=SqlAlchemyPriceItemRepository(session),
            embeddings=_catalog_embeddings(settings),
            vector_search=QdrantCatalogSearch(
                qdrant,
                settings.catalog_qdrant_collection,
            ),
            catalog_query_prefix=settings.catalog_query_prefix,
            catalog_embedding_template_version=(
                settings.catalog_embedding_template_version
            ),
        )
    finally:
        await qdrant.close()


# ---------------------------------------------------------------------------
# Assistant use cases
# ---------------------------------------------------------------------------


def get_chat_turn_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    search: Annotated[SearchPriceItemsUseCase, Depends(get_search_price_items_uc)],
    details: Annotated[GetPriceItemUseCase, Depends(get_get_price_item_uc)],
) -> AssistantGraphRunner:
    catalog_search = CatalogSearchToolAdapter(search)
    item_details = CatalogItemDetailsToolAdapter(details)
    planner = (
        DemoAssistantAgentPlanner()
        if settings.argus_demo_mode
        else LangChainAssistantAgentPlanner(
            base_url=settings.lm_studio_url,
            model=settings.lm_studio_llm_model,
            timeout=settings.assistant_agent_timeout_seconds,
            api_key=settings.api_key or "not-needed",
        )
    )
    return AssistantGraphRunner(
        planner=planner,
        catalog_search=catalog_search,
        item_details=item_details,
        supplier_verification=ManualNotVerifiedSupplierVerificationAdapter(),
        max_tool_calls_per_turn=settings.assistant_agent_max_tool_calls_per_turn,
        max_iterations=settings.assistant_agent_max_iterations,
    )


# ---------------------------------------------------------------------------
# Ingest use cases
# ---------------------------------------------------------------------------


def get_upload_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
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
    session: Annotated[AsyncSession, Depends(_session)],
) -> GetDocumentUseCase:
    return GetDocumentUseCase(documents=SqlAlchemyDocumentRepository(session))


def get_list_documents_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> ListDocumentsUseCase:
    return ListDocumentsUseCase(documents=SqlAlchemyDocumentRepository(session))


def get_document_facts_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> GetDocumentFactsUseCase:
    return GetDocumentFactsUseCase(
        documents=SqlAlchemyDocumentRepository(session),
        fields=SqlAlchemyFieldsRepository(session),
        summaries=SqlAlchemySummaryRepository(session),
    )


def get_document_preview_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> GetDocumentPreviewUseCase:
    return GetDocumentPreviewUseCase(documents=SqlAlchemyDocumentRepository(session))


def get_update_document_facts_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> UpdateDocumentFactsUseCase:
    return UpdateDocumentFactsUseCase(
        fields=SqlAlchemyFieldsRepository(session),
        summaries=SqlAlchemySummaryRepository(session),
        uow=SessionUnitOfWork(session),
    )


def get_delete_document_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(
        documents=SqlAlchemyDocumentRepository(session),
        vectors=QdrantVectorIndex(qdrant, settings.document_qdrant_collection),
        uow=SessionUnitOfWork(session),
    )


def get_search_within_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> SearchWithinDocumentUseCase:
    return SearchWithinDocumentUseCase(
        embeddings=_document_embeddings(settings),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
    )


# ---------------------------------------------------------------------------
# Contractors use cases
# ---------------------------------------------------------------------------


def get_contractor_profile_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> GetContractorProfileUseCase:
    return GetContractorProfileUseCase(
        contractors=SqlAlchemyContractorRepository(session),
        mappings=SqlAlchemyRawContractorMappingRepository(session),
    )


def get_list_contractors_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> ListContractorsUseCase:
    return ListContractorsUseCase(
        contractors=SqlAlchemyContractorRepository(session),
    )


def get_list_contractor_documents_uc(
    session: Annotated[AsyncSession, Depends(_session)],
) -> ListContractorDocumentsUseCase:
    return ListContractorDocumentsUseCase(
        contractors=SqlAlchemyContractorRepository(session),
    )


def get_search_documents_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> SearchDocumentsUseCase:
    return SearchDocumentsUseCase(
        embeddings=_document_embeddings(settings),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
        documents=SqlAlchemyDocumentRepository(session),
    )


# ---------------------------------------------------------------------------
# Search use cases
# ---------------------------------------------------------------------------


def get_search_contractors_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> SearchContractorsUseCase:
    return SearchContractorsUseCase(
        embeddings=_document_embeddings(settings),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
        contractors=SqlAlchemyContractorRepository(session),
    )


def get_global_rag_answer_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> AnswerGlobalSearchUseCase:
    return AnswerGlobalSearchUseCase(
        embeddings=_document_embeddings(settings),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
        contractors=SqlAlchemyContractorRepository(session),
        documents=SqlAlchemyDocumentRepository(session),
        llm=_rag_llm(settings),
        similarity_top_k=settings.rag_similarity_top_k,
        context_top_k=settings.rag_context_top_k,
    )


def get_contractor_rag_answer_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> AnswerContractorUseCase:
    return AnswerContractorUseCase(
        embeddings=_document_embeddings(settings),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
        contractors=SqlAlchemyContractorRepository(session),
        documents=SqlAlchemyDocumentRepository(session),
        llm=_rag_llm(settings),
        similarity_top_k=settings.rag_similarity_top_k,
        context_top_k=settings.rag_context_top_k,
    )


def get_document_rag_answer_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> AnswerDocumentUseCase:
    return AnswerDocumentUseCase(
        embeddings=_document_embeddings(settings),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
        documents=SqlAlchemyDocumentRepository(session),
        fields=SqlAlchemyFieldsRepository(session),
        summaries=SqlAlchemySummaryRepository(session),
        llm=_rag_llm(settings),
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
    "get_index_price_items_uc",
    "get_list_contractors_uc",
    "get_list_contractor_documents_uc",
    "get_list_documents_uc",
    "get_list_price_items_uc",
    "get_qdrant_client",
    "get_search_price_items_uc",
    "get_search_contractors_uc",
    "get_search_documents_uc",
    "get_search_within_uc",
    "get_sessionmaker",
    "get_update_document_facts_uc",
    "get_upload_uc",
]
