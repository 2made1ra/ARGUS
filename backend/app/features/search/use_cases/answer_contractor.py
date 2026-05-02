from __future__ import annotations

from uuid import UUID

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.contractors.ports import ContractorRepository
from app.features.ingest.ports import DocumentRepository, EmbeddingService
from app.features.search.dto import ChatMessage, RagAnswer, SearchHit
from app.features.search.ports import ChatLLM, Reranker, VectorSearch
from app.features.search.prompts import build_contractor_answer_messages
from app.features.search.use_cases.rag_common import (
    NO_EVIDENCE_ANSWER,
    context_from_hit,
    document_ids_from_hits,
    select_contexts,
    sorted_hits,
)


class AnswerContractorUseCase:
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
        contractor_id: ContractorEntityId,
        message: str,
        history: list[ChatMessage],
    ) -> RagAnswer:
        contractor = await self._contractors.get(contractor_id)
        document_count = await self._contractors.count_documents_for(contractor_id)
        [query_vector] = await self._embeddings.embed([message])
        results = await self._vectors.search(
            query_vector=query_vector,
            limit=self._similarity_top_k,
            filter={
                "must": [
                    {
                        "key": "contractor_entity_id",
                        "match": {"value": str(contractor_id)},
                    },
                ],
            },
        )
        hits = sorted_hits([hit for hit in results if isinstance(hit, SearchHit)])
        documents = await self._documents.get_many(document_ids_from_hits(hits))
        contexts = []
        for hit in hits:
            document_id = _document_id_from_payload(hit)
            context = context_from_hit(
                hit,
                source_index=0,
                contractor=contractor,
                document=documents.get(document_id) if document_id is not None else None,
                contractor_id=contractor_id,
            )
            if context is not None:
                contexts.append(context)
        selected_contexts = await select_contexts(
            query=message,
            chunks=contexts,
            top_k=self._context_top_k,
            reranker=self._reranker,
        )
        if not selected_contexts:
            return RagAnswer(
                answer=(
                    f"По подрядчику {contractor.display_name} найдено договоров: "
                    f"{document_count}. В индексированных фрагментах недостаточно "
                    "данных для ответа на этот вопрос."
                ),
                sources=[],
            )

        answer = await self._llm.complete(
            build_contractor_answer_messages(
                message=message,
                contractor_name=contractor.display_name,
                document_count=document_count,
                contexts=selected_contexts,
                history=history,
            ),
        )
        return RagAnswer(
            answer=answer or NO_EVIDENCE_ANSWER,
            sources=[context.source for context in selected_contexts],
        )


def _document_id_from_payload(hit: SearchHit) -> DocumentId | None:
    value = hit.payload.get("document_id")
    return None if value is None else DocumentId(UUID(str(value)))


__all__ = ["AnswerContractorUseCase"]
