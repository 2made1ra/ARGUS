from __future__ import annotations

from uuid import UUID

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.contractors.ports import ContractorRepository
from app.features.ingest.ports import DocumentRepository, EmbeddingService
from app.features.search.dto import (
    ChatMessage,
    GlobalRagAnswer,
    RagContractorResult,
    SearchGroup,
    SearchHit,
)
from app.features.search.ports import ChatLLM, Reranker, VectorSearch
from app.features.search.prompts import build_global_answer_messages
from app.features.search.use_cases.rag_common import (
    NO_EVIDENCE_ANSWER,
    context_from_hit,
    document_ids_from_hits,
    select_contexts,
)

_GROUP_SIZE = 3
_SNIPPET_LENGTH = 240


class AnswerGlobalSearchUseCase:
    def __init__(
        self,
        *,
        embeddings: EmbeddingService,
        vectors: VectorSearch,
        contractors: ContractorRepository,
        documents: DocumentRepository,
        llm: ChatLLM,
        similarity_top_k: int = 15,
        context_top_k: int = 5,
        reranker: Reranker | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._vectors = vectors
        self._contractors = contractors
        self._documents = documents
        self._llm = llm
        self._similarity_top_k = similarity_top_k
        self._context_top_k = context_top_k
        self._reranker = reranker

    async def execute(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        limit: int = 10,
    ) -> GlobalRagAnswer:
        [query_vector] = await self._embeddings.embed([message])
        groups = await self._vectors.search(
            query_vector=query_vector,
            limit=max(self._similarity_top_k, limit),
            group_by="contractor_entity_id",
            group_size=_GROUP_SIZE,
        )
        search_groups = [group for group in groups if isinstance(group, SearchGroup)]
        if not search_groups:
            return GlobalRagAnswer(answer=NO_EVIDENCE_ANSWER, contractors=[], sources=[])

        contractor_ids = [_contractor_id_from_group(group) for group in search_groups]
        contractors = await self._contractors.get_many(contractor_ids)
        document_counts = await self._contractors.count_documents_for_many(
            contractor_ids,
        )
        all_hits = [hit for group in search_groups for hit in group.hits]
        documents = await self._documents.get_many(document_ids_from_hits(all_hits))

        contractor_results: list[RagContractorResult] = []
        contexts = []
        for group in search_groups:
            contractor_id = _contractor_id_from_group(group)
            contractor = contractors.get(contractor_id)
            if contractor is None or not group.hits:
                continue
            top_hit = max(group.hits, key=lambda hit: hit.score)
            contractor_results.append(
                RagContractorResult(
                    contractor_id=contractor_id,
                    name=contractor.display_name,
                    score=top_hit.score,
                    matched_chunks_count=len(group.hits),
                    document_count=document_counts.get(contractor_id, 0),
                    top_snippet=str(top_hit.payload.get("text") or "")[
                        :_SNIPPET_LENGTH
                    ],
                ),
            )
            for hit in group.hits:
                document_id = _document_id_from_hit(hit)
                context = context_from_hit(
                    hit,
                    source_index=0,
                    contractor=contractor,
                    document=documents.get(document_id) if document_id else None,
                    contractor_id=contractor_id,
                )
                if context is not None:
                    contexts.append(context)

        contractor_results.sort(key=lambda result: result.score, reverse=True)
        contexts = sorted(contexts, key=lambda context: context.source.score, reverse=True)
        selected_contexts = await select_contexts(
            query=message,
            chunks=contexts,
            top_k=self._context_top_k,
            reranker=self._reranker,
        )
        if not selected_contexts:
            return GlobalRagAnswer(
                answer=NO_EVIDENCE_ANSWER,
                contractors=contractor_results[:limit],
                sources=[],
            )

        answer = await self._llm.complete(
            build_global_answer_messages(
                message=message,
                contexts=selected_contexts,
                history=history,
            ),
        )
        return GlobalRagAnswer(
            answer=answer or NO_EVIDENCE_ANSWER,
            contractors=contractor_results[:limit],
            sources=[context.source for context in selected_contexts],
        )


def _contractor_id_from_group(group: SearchGroup) -> ContractorEntityId:
    return ContractorEntityId(UUID(group.group_key))


def _document_id_from_hit(hit: SearchHit) -> DocumentId | None:
    value = hit.payload.get("document_id")
    if value is None:
        return None
    return DocumentId(UUID(str(value)))


__all__ = ["AnswerGlobalSearchUseCase"]
