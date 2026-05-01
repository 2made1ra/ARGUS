from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.ports import DocumentRepository, EmbeddingService
from app.features.search.dto import ChunkSnippet, DocumentSearchResult, SearchGroup
from app.features.search.ports import VectorSearch

_QDRANT_GROUP_LIMIT = 100
_QDRANT_GROUP_SIZE = 3


class SearchDocumentsUseCase:
    def __init__(
        self,
        *,
        embeddings: EmbeddingService,
        vectors: VectorSearch,
        documents: DocumentRepository,
    ) -> None:
        self._embeddings = embeddings
        self._vectors = vectors
        self._documents = documents

    async def execute(
        self,
        *,
        contractor_entity_id: ContractorEntityId,
        query: str,
        limit: int = 20,
    ) -> list[DocumentSearchResult]:
        [query_vector] = await self._embeddings.embed([query])
        groups = await self._vectors.search(
            query_vector=query_vector,
            limit=_QDRANT_GROUP_LIMIT,
            filter={
                "must": [
                    {
                        "key": "contractor_entity_id",
                        "match": {"value": str(contractor_entity_id)},
                    },
                ],
            },
            group_by="document_id",
            group_size=_QDRANT_GROUP_SIZE,
        )

        results: list[tuple[float, DocumentSearchResult]] = []
        for group in [group for group in groups if isinstance(group, SearchGroup)]:
            if not group.hits:
                continue

            document_id = _document_id_from_group(group)
            document = await self._documents.get(document_id)
            snippets = [
                ChunkSnippet(
                    page=_optional_int(hit.payload.get("page_start")),
                    snippet=str(hit.payload["text"]),
                    score=hit.score,
                )
                for hit in group.hits
            ]
            score = max(hit.score for hit in group.hits)
            results.append(
                (
                    score,
                    DocumentSearchResult(
                        document_id=document_id,
                        title=document.title,
                        date=document.created_at.date().isoformat(),
                        matched_chunks=snippets,
                    ),
                ),
            )

        sorted_results = sorted(results, key=lambda item: item[0], reverse=True)
        return [result for _, result in sorted_results[:limit]]


def _document_id_from_group(group: SearchGroup) -> DocumentId:
    return DocumentId(UUID(group.group_key))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


__all__ = ["SearchDocumentsUseCase"]
