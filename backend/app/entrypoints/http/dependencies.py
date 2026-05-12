from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.celery.task_queue import CeleryIngestionTaskQueue
from app.adapters.llm.assistant_router import LMStudioAssistantRouterAdapter
from app.adapters.llm.chat import LMStudioChatClient
from app.adapters.llm.embeddings import LMStudioEmbeddings
from app.adapters.local_fs.file_storage import LocalFileStorage
from app.adapters.qdrant.catalog_index import QdrantCatalogIndex
from app.adapters.qdrant.catalog_search import QdrantCatalogSearch
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
from app.adapters.supplier_verification.manual import (
    ManualNotVerifiedSupplierVerificationAdapter,
)
from app.config import Settings, get_settings
from app.entrypoints.http.session import _session, get_qdrant_client, get_sessionmaker
from app.features.assistant.domain.tool_executor import ToolExecutor
from app.features.assistant.dto import (
    CatalogItemDetail,
    CatalogSearchFilters,
    FoundCatalogItem,
)
from app.features.assistant.dto import MatchReason as AssistantMatchReason
from app.features.assistant.router import HeuristicAssistantRouter
from app.features.assistant.use_cases.chat_turn import ChatTurnUseCase
from app.features.catalog.dto import FoundPriceItem, SearchPriceItemsFilters
from app.features.catalog.ports import PriceItemNotFound
from app.features.catalog.use_cases.get_price_item import GetPriceItemUseCase
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase
from app.features.catalog.use_cases.index_price_items import IndexPriceItemsUseCase
from app.features.catalog.use_cases.list_price_items import ListPriceItemsUseCase
from app.features.catalog.use_cases.search_price_items import SearchPriceItemsUseCase
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
        embedding_model=settings.catalog_embedding_model,
    )


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
        embeddings=LMStudioEmbeddings(
            base_url=settings.lm_studio_url,
            model=settings.catalog_embedding_model,
            embedding_dim=settings.catalog_embedding_dim,
        ),
        index=QdrantCatalogIndex(qdrant, settings.catalog_qdrant_collection),
        uow=SessionUnitOfWork(session),
        catalog_embedding_model=settings.catalog_embedding_model,
        catalog_embedding_dim=settings.catalog_embedding_dim,
        catalog_embedding_template_version=settings.catalog_embedding_template_version,
        catalog_document_prefix=settings.catalog_document_prefix,
    )


def get_search_price_items_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(_session)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
) -> SearchPriceItemsUseCase:
    return SearchPriceItemsUseCase(
        items=SqlAlchemyPriceItemRepository(session),
        embeddings=LMStudioEmbeddings(
            base_url=settings.lm_studio_url,
            model=settings.catalog_embedding_model,
            embedding_dim=settings.catalog_embedding_dim,
        ),
        vector_search=QdrantCatalogSearch(qdrant, settings.catalog_qdrant_collection),
        catalog_query_prefix=settings.catalog_query_prefix,
        catalog_embedding_template_version=settings.catalog_embedding_template_version,
    )


# ---------------------------------------------------------------------------
# Assistant use cases
# ---------------------------------------------------------------------------


class _CatalogSearchToolAdapter:
    def __init__(self, search: SearchPriceItemsUseCase) -> None:
        self._search = search

    async def search_items(
        self,
        *,
        query: str,
        limit: int,
        filters: CatalogSearchFilters | None = None,
    ) -> list[FoundCatalogItem]:
        result = await self._search.search_items(
            query=query,
            filters=_catalog_search_filters(filters),
            limit=limit,
        )
        return [_found_catalog_item(item) for item in result.items]


class _CatalogItemDetailsToolAdapter:
    def __init__(self, details: GetPriceItemUseCase) -> None:
        self._details = details

    async def get_item_details(
        self,
        *,
        item_id: UUID,
    ) -> CatalogItemDetail | None:
        try:
            item, _sources = await self._details.execute(item_id)
        except PriceItemNotFound:
            return None
        return CatalogItemDetail(
            id=item.id,
            name=item.name,
            category=item.category,
            unit=item.unit,
            unit_price=item.unit_price,
            supplier=item.supplier,
            supplier_inn=item.supplier_inn,
            supplier_city=item.supplier_city,
            supplier_phone=item.supplier_phone,
            supplier_email=item.supplier_email,
            supplier_status=item.supplier_status,
            source_text=item.source_text,
        )


def _found_catalog_item(item: FoundPriceItem) -> FoundCatalogItem:
    return FoundCatalogItem(
        id=item.id,
        score=item.score,
        name=item.name,
        category=item.category,
        unit=item.unit,
        unit_price=item.unit_price,
        supplier=item.supplier,
        supplier_city=item.supplier_city,
        source_text_snippet=item.source_text_snippet,
        source_text_full_available=item.source_text_full_available,
        match_reason=AssistantMatchReason(
            code=item.match_reason.code,
            label=item.match_reason.label,
        ),
    )


def _catalog_search_filters(
    filters: CatalogSearchFilters | None,
) -> SearchPriceItemsFilters:
    if filters is None:
        return SearchPriceItemsFilters()
    return SearchPriceItemsFilters(
        supplier_city_normalized=filters.supplier_city_normalized,
        category=filters.category,
        supplier_status_normalized=filters.supplier_status_normalized,
        has_vat=filters.has_vat,
        vat_mode=filters.vat_mode,
        unit_price_min=_decimal_or_none(filters.unit_price_min),
        unit_price_max=_decimal_or_none(filters.unit_price_max),
    )


def _decimal_or_none(value: int | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def get_chat_turn_uc(
    settings: Annotated[Settings, Depends(get_settings)],
    search: Annotated[SearchPriceItemsUseCase, Depends(get_search_price_items_uc)],
    details: Annotated[GetPriceItemUseCase, Depends(get_get_price_item_uc)],
) -> ChatTurnUseCase:
    catalog_search = _CatalogSearchToolAdapter(search)
    item_details = _CatalogItemDetailsToolAdapter(details)
    return ChatTurnUseCase(
        router=HeuristicAssistantRouter(
            llm_router=LMStudioAssistantRouterAdapter(
                base_url=settings.lm_studio_url,
                model=settings.lm_studio_llm_model,
            ),
        ),
        tool_executor=ToolExecutor(
            catalog_search=catalog_search,
            item_details=item_details,
            supplier_verification=ManualNotVerifiedSupplierVerificationAdapter(),
        ),
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
        vectors=QdrantVectorIndex(qdrant, settings.document_qdrant_collection),
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
            embedding_dim=settings.document_embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
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
            embedding_dim=settings.document_embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
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
            embedding_dim=settings.document_embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
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
            embedding_dim=settings.document_embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
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
            embedding_dim=settings.document_embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
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
            embedding_dim=settings.document_embedding_dim,
        ),
        vectors=QdrantVectorSearch(qdrant, settings.document_qdrant_collection),
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
