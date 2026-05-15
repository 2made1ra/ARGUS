from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

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


class DocumentRagGraphState(TypedDict, total=False):
    document_id: DocumentId
    message: str
    history: list[ChatMessage]
    document: Any
    summary_text: str | None
    fields_dict: dict[str, Any]
    query_vector: list[float]
    hits: list[SearchHit]
    contexts: list
    selected_contexts: list
    answer_text: str
    response: RagAnswer


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
        self._graph = self._build_graph()

    async def execute(
        self,
        *,
        document_id: DocumentId,
        message: str,
        history: list[ChatMessage],
    ) -> RagAnswer:
        result = await self._graph.ainvoke(
            {
                "document_id": document_id,
                "message": message,
                "history": history,
            },
        )
        return result["response"]

    def _build_graph(self) -> object:
        graph = StateGraph(DocumentRagGraphState)
        graph.add_node("load_document_context", self._load_document_context)
        graph.add_node("embed_query", self._embed_query)
        graph.add_node("vector_search", self._vector_search)
        graph.add_node("hydrate_sources", self._hydrate_sources)
        graph.add_node("select_contexts", self._select_contexts)
        graph.add_node("generate_answer", self._generate_answer)
        graph.add_node("format_response", self._format_response)
        graph.add_edge(START, "load_document_context")
        graph.add_edge("load_document_context", "embed_query")
        graph.add_edge("embed_query", "vector_search")
        graph.add_edge("vector_search", "hydrate_sources")
        graph.add_edge("hydrate_sources", "select_contexts")
        graph.add_conditional_edges(
            "select_contexts",
            self._next_after_context_selection,
            {
                "generate_answer": "generate_answer",
                "format_response": "format_response",
            },
        )
        graph.add_edge("generate_answer", "format_response")
        graph.add_edge("format_response", END)
        return graph.compile()

    async def _load_document_context(
        self,
        state: DocumentRagGraphState,
    ) -> DocumentRagGraphState:
        document = await self._documents.get(state["document_id"])
        fields = await self._fields.get(state["document_id"])
        summary = await self._summaries.get(state["document_id"])
        summary_text = summary[0] if summary is not None else None
        fields_dict = fields.model_dump() if fields is not None else {}
        return {
            "document": document,
            "summary_text": summary_text,
            "fields_dict": fields_dict,
        }

    async def _embed_query(
        self,
        state: DocumentRagGraphState,
    ) -> DocumentRagGraphState:
        [query_vector] = await self._embeddings.embed([state["message"]])
        return {"query_vector": query_vector}

    async def _vector_search(
        self,
        state: DocumentRagGraphState,
    ) -> DocumentRagGraphState:
        results = await self._vectors.search(
            query_vector=state["query_vector"],
            limit=self._similarity_top_k,
            filter={
                "must": [
                    {
                        "key": "document_id",
                        "match": {"value": str(state["document_id"])},
                    },
                ],
            },
        )
        hits = sorted_hits([hit for hit in results if isinstance(hit, SearchHit)])
        return {"hits": hits}

    async def _hydrate_sources(
        self,
        state: DocumentRagGraphState,
    ) -> DocumentRagGraphState:
        document = state["document"]
        contexts = [
            context
            for hit in state.get("hits", [])
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
        return {"contexts": contexts}

    async def _select_contexts(
        self,
        state: DocumentRagGraphState,
    ) -> DocumentRagGraphState:
        selected_contexts = await select_contexts(
            query=state["message"],
            chunks=state.get("contexts", []),
            top_k=self._context_top_k,
            reranker=self._reranker,
        )
        return {"selected_contexts": selected_contexts}

    def _next_after_context_selection(self, state: DocumentRagGraphState) -> str:
        if state.get("selected_contexts") or _has_document_context(state):
            return "generate_answer"
        return "format_response"

    async def _generate_answer(
        self,
        state: DocumentRagGraphState,
    ) -> DocumentRagGraphState:
        answer = await self._llm.complete(
            build_document_answer_messages(
                message=state["message"],
                document_title=state["document"].title,
                summary=state.get("summary_text"),
                fields=state.get("fields_dict", {}),
                contexts=state.get("selected_contexts", []),
                history=state["history"],
            ),
        )
        return {"answer_text": answer}

    async def _format_response(
        self,
        state: DocumentRagGraphState,
    ) -> DocumentRagGraphState:
        selected_contexts = state.get("selected_contexts", [])
        if not selected_contexts and not _has_document_context(state):
            response = RagAnswer(answer=NO_EVIDENCE_ANSWER, sources=[])
        else:
            response = RagAnswer(
                answer=state.get("answer_text") or NO_EVIDENCE_ANSWER,
                sources=[context.source for context in selected_contexts],
            )
        return {"response": response}


def _has_document_context(state: DocumentRagGraphState) -> bool:
    summary_text = state.get("summary_text")
    fields_dict = state.get("fields_dict", {})
    has_fields = any(value not in {None, ""} for value in fields_dict.values())
    return bool(summary_text or has_fields)


__all__ = ["AnswerDocumentUseCase"]
