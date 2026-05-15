from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

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


class ContractorRagGraphState(TypedDict, total=False):
    contractor_id: ContractorEntityId
    message: str
    history: list[ChatMessage]
    contractor: Any
    contractor_name: str
    document_count: int
    query_vector: list[float]
    hits: list[SearchHit]
    contexts: list
    selected_contexts: list
    answer_text: str
    response: RagAnswer


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
        self._graph = self._build_graph()

    async def execute(
        self,
        *,
        contractor_id: ContractorEntityId,
        message: str,
        history: list[ChatMessage],
    ) -> RagAnswer:
        result = await self._graph.ainvoke(
            {
                "contractor_id": contractor_id,
                "message": message,
                "history": history,
            },
        )
        return result["response"]

    def _build_graph(self) -> object:
        graph = StateGraph(ContractorRagGraphState)
        graph.add_node("load_contractor", self._load_contractor)
        graph.add_node("embed_query", self._embed_query)
        graph.add_node("vector_search", self._vector_search)
        graph.add_node("hydrate_sources", self._hydrate_sources)
        graph.add_node("select_contexts", self._select_contexts)
        graph.add_node("generate_answer", self._generate_answer)
        graph.add_node("format_response", self._format_response)
        graph.add_edge(START, "load_contractor")
        graph.add_edge("load_contractor", "embed_query")
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

    async def _load_contractor(
        self,
        state: ContractorRagGraphState,
    ) -> ContractorRagGraphState:
        contractor = await self._contractors.get(state["contractor_id"])
        document_count = await self._contractors.count_documents_for(
            state["contractor_id"],
        )
        return {
            "contractor": contractor,
            "contractor_name": contractor.display_name,
            "document_count": document_count,
        }

    async def _embed_query(
        self,
        state: ContractorRagGraphState,
    ) -> ContractorRagGraphState:
        [query_vector] = await self._embeddings.embed([state["message"]])
        return {"query_vector": query_vector}

    async def _vector_search(
        self,
        state: ContractorRagGraphState,
    ) -> ContractorRagGraphState:
        results = await self._vectors.search(
            query_vector=state["query_vector"],
            limit=self._similarity_top_k,
            filter={
                "must": [
                    {
                        "key": "contractor_entity_id",
                        "match": {"value": str(state["contractor_id"])},
                    },
                ],
            },
        )
        hits = sorted_hits([hit for hit in results if isinstance(hit, SearchHit)])
        return {"hits": hits}

    async def _hydrate_sources(
        self,
        state: ContractorRagGraphState,
    ) -> ContractorRagGraphState:
        hits = state.get("hits", [])
        documents = await self._documents.get_many(document_ids_from_hits(hits))
        contexts = []
        for hit in hits:
            document_id = _document_id_from_payload(hit)
            document = documents.get(document_id) if document_id is not None else None
            context = context_from_hit(
                hit,
                source_index=0,
                contractor=state.get("contractor"),
                document=document,
                contractor_id=state["contractor_id"],
            )
            if context is not None:
                contexts.append(context)
        return {"contexts": contexts}

    async def _select_contexts(
        self,
        state: ContractorRagGraphState,
    ) -> ContractorRagGraphState:
        selected_contexts = await select_contexts(
            query=state["message"],
            chunks=state.get("contexts", []),
            top_k=self._context_top_k,
            reranker=self._reranker,
        )
        return {"selected_contexts": selected_contexts}

    def _next_after_context_selection(self, state: ContractorRagGraphState) -> str:
        if state.get("selected_contexts"):
            return "generate_answer"
        return "format_response"

    async def _generate_answer(
        self,
        state: ContractorRagGraphState,
    ) -> ContractorRagGraphState:
        answer = await self._llm.complete(
            build_contractor_answer_messages(
                message=state["message"],
                contractor_name=state["contractor_name"],
                document_count=state["document_count"],
                contexts=state.get("selected_contexts", []),
                history=state["history"],
            ),
        )
        return {"answer_text": answer}

    async def _format_response(
        self,
        state: ContractorRagGraphState,
    ) -> ContractorRagGraphState:
        selected_contexts = state.get("selected_contexts", [])
        if not selected_contexts:
            response = RagAnswer(
                answer=(
                    f"По подрядчику {state['contractor_name']} найдено договоров: "
                    f"{state['document_count']}. В индексированных фрагментах "
                    "недостаточно "
                    "данных для ответа на этот вопрос."
                ),
                sources=[],
            )
        else:
            response = RagAnswer(
                answer=state.get("answer_text") or NO_EVIDENCE_ANSWER,
                sources=[context.source for context in selected_contexts],
            )
        return {"response": response}


def _document_id_from_payload(hit: SearchHit) -> DocumentId | None:
    value = hit.payload.get("document_id")
    return None if value is None else DocumentId(UUID(str(value)))


__all__ = ["AnswerContractorUseCase"]
