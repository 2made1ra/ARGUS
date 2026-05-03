from __future__ import annotations

from app.core.domain.ids import DocumentId
from app.features.ingest.ports import (
    DocumentRepository,
    EmbeddingService,
    FieldsRepository,
    SummaryRepository,
)
from app.features.search.dto import ChatMessage, RagAnswer, SearchHit
from app.features.search.ports import ChatLLM, Reranker, VectorSearch
from app.features.search.prompts import build_document_answer_messages
from app.features.search.use_cases.rag_common import (
    NO_EVIDENCE_ANSWER,
    context_from_hit,
    select_contexts,
    sorted_hits,
)


class AnswerDocumentUseCase:
    def __init__(
        self,
        *,
        embeddings: EmbeddingService,
        vectors: VectorSearch,
        documents: DocumentRepository,
        fields: FieldsRepository,
        summaries: SummaryRepository,
        llm: ChatLLM,
        similarity_top_k: int = 15,
        context_top_k: int = 5,
        reranker: Reranker | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._vectors = vectors
        self._documents = documents
        self._fields = fields
        self._summaries = summaries
        self._llm = llm
        self._similarity_top_k = similarity_top_k
        self._context_top_k = context_top_k
        self._reranker = reranker

    async def execute(
        self,
        *,
        document_id: DocumentId,
        message: str,
        history: list[ChatMessage],
    ) -> RagAnswer:
        document = await self._documents.get(document_id)
        fields = await self._fields.get(document_id)
        summary = await self._summaries.get(document_id)
        [query_vector] = await self._embeddings.embed([message])
        results = await self._vectors.search(
            query_vector=query_vector,
            limit=self._similarity_top_k,
            filter={
                "must": [
                    {
                        "key": "document_id",
                        "match": {"value": str(document_id)},
                    },
                ],
            },
        )
        hits = sorted_hits([hit for hit in results if isinstance(hit, SearchHit)])
        contexts = [
            context
            for hit in hits
            if (
                context := context_from_hit(
                    hit,
                    source_index=0,
                    document=document,
                    contractor_id=document.contractor_entity_id,
                )
            )
            is not None
        ]
        selected_contexts = await select_contexts(
            query=message,
            chunks=contexts,
            top_k=self._context_top_k,
            reranker=self._reranker,
        )
        summary_text = summary[0] if summary is not None else None
        fields_dict = fields.model_dump() if fields is not None else {}
        has_fields = any(value not in {None, ""} for value in fields_dict.values())
        if not selected_contexts and not summary_text and not has_fields:
            return RagAnswer(answer=NO_EVIDENCE_ANSWER, sources=[])

        answer = await self._llm.complete(
            build_document_answer_messages(
                message=message,
                document_title=document.title,
                summary=summary_text,
                fields=fields_dict,
                contexts=selected_contexts,
                history=history,
            ),
        )
        return RagAnswer(
            answer=answer or NO_EVIDENCE_ANSWER,
            sources=[context.source for context in selected_contexts],
        )


__all__ = ["AnswerDocumentUseCase"]
