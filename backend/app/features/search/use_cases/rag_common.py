from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.contractors.entities.contractor import Contractor
from app.features.ingest.entities.document import Document
from app.features.search.dto import RagContextChunk, SearchHit, SourceRef
from app.features.search.ports import Reranker
from app.features.search.use_cases.payload_values import optional_int

NO_EVIDENCE_ANSWER = (
    "В загруженных документах недостаточно данных для ответа. "
    "Попробуйте уточнить запрос или загрузить больше договоров."
)
_MAX_CONTEXT_TEXT = 1600
_MAX_SOURCE_SNIPPET = 500


async def select_contexts(
    *,
    query: str,
    chunks: list[RagContextChunk],
    top_k: int,
    reranker: Reranker | None,
) -> list[RagContextChunk]:
    if reranker is None:
        selected = chunks[:top_k]
    else:
        selected = await reranker.rerank(query=query, chunks=chunks, top_k=top_k)
    return [
        RagContextChunk(
            source_index=index,
            source=context.source,
            text=context.text,
        )
        for index, context in enumerate(selected, start=1)
    ]


def context_from_hit(
    hit: SearchHit,
    *,
    source_index: int,
    contractor: Contractor | None = None,
    document: Document | None = None,
    contractor_id: ContractorEntityId | None = None,
) -> RagContextChunk | None:
    document_id = _document_id(hit.payload.get("document_id"))
    if document_id is None:
        return None

    resolved_contractor_id = contractor_id or _contractor_id(
        hit.payload.get("contractor_entity_id"),
    )
    text = str(hit.payload.get("text") or "").strip()
    if not text:
        return None

    return RagContextChunk(
        source_index=source_index,
        source=SourceRef(
            document_id=document_id,
            contractor_id=resolved_contractor_id,
            page_start=optional_int(hit.payload.get("page_start")),
            page_end=optional_int(hit.payload.get("page_end")),
            chunk_index=int(hit.payload.get("chunk_index") or 0),
            score=hit.score,
            snippet=text[:_MAX_SOURCE_SNIPPET],
            document_title=document.title if document is not None else None,
            contractor_name=contractor.display_name if contractor is not None else None,
        ),
        text=text[:_MAX_CONTEXT_TEXT],
    )


def sorted_hits(hits: list[SearchHit]) -> list[SearchHit]:
    return sorted(hits, key=lambda hit: hit.score, reverse=True)


def document_ids_from_hits(hits: list[SearchHit]) -> list[DocumentId]:
    ids: list[DocumentId] = []
    seen: set[DocumentId] = set()
    for hit in hits:
        document_id = _document_id(hit.payload.get("document_id"))
        if document_id is not None and document_id not in seen:
            ids.append(document_id)
            seen.add(document_id)
    return ids


def _document_id(value: Any) -> DocumentId | None:
    parsed = _uuid(value)
    return DocumentId(parsed) if parsed is not None else None


def _contractor_id(value: Any) -> ContractorEntityId | None:
    parsed = _uuid(value)
    return ContractorEntityId(parsed) if parsed is not None else None


def _uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except ValueError:
        return None


__all__ = [
    "NO_EVIDENCE_ANSWER",
    "context_from_hit",
    "document_ids_from_hits",
    "select_contexts",
    "sorted_hits",
]
