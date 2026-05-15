from __future__ import annotations

from typing import Any

from app.core.domain.ids import DocumentId
from app.features.ingest.ports import EmbeddingService
from app.features.search.dto import SearchHit, WithinDocumentResult
from app.features.search.ports import VectorSearch
from app.features.search.use_cases.payload_values import optional_int


class SearchWithinDocumentUseCase:
    def __init__(
        self,
        *,
        embeddings: EmbeddingService,
        vectors: VectorSearch,
    ) -> None:
        self._embeddings = embeddings
        self._vectors = vectors

    async def execute(
        self,
        *,
        document_id: DocumentId,
        query: str,
        limit: int = 20,
    ) -> list[WithinDocumentResult]:
        [query_vector] = await self._embeddings.embed([query])
        hits = await self._vectors.search(
            query_vector=query_vector,
            limit=limit,
            filter={
                "must": [
                    {
                        "key": "document_id",
                        "match": {"value": str(document_id)},
                    },
                ],
                "must_not": [
                    {
                        "key": "is_summary",
                        "match": {"value": True},
                    },
                ],
            },
        )

        return [
            _result_from_hit(hit)
            for hit in hits
            if isinstance(hit, SearchHit) and hit.payload.get("is_summary") is not True
        ]


def _result_from_hit(hit: SearchHit) -> WithinDocumentResult:
    return WithinDocumentResult(
        chunk_index=int(hit.payload["chunk_index"]),
        page_start=optional_int(hit.payload.get("page_start")),
        page_end=optional_int(hit.payload.get("page_end")),
        section_type=_optional_str(hit.payload.get("section_type")),
        snippet=str(hit.payload["text"]),
        score=hit.score,
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = ["SearchWithinDocumentUseCase"]
