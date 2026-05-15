from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

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


class GlobalRagGraphState(TypedDict, total=False):
    message: str
    history: list[ChatMessage]
    limit: int
    query_vector: list[float]
    search_groups: list[SearchGroup]
    contractor_results: list[RagContractorResult]
    contexts: list
    selected_contexts: list
    answer_text: str
    response: GlobalRagAnswer


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
        self._graph = self._build_graph()

    async def execute(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        limit: int = 10,
    ) -> GlobalRagAnswer:
        result = await self._graph.ainvoke(
            {
                "message": message,
                "history": history,
                "limit": limit,
            },
        )
        return result["response"]

    def _build_graph(self) -> object:
        graph = StateGraph(GlobalRagGraphState)
        graph.add_node("embed_query", self._embed_query)
        graph.add_node("vector_search", self._vector_search)
        graph.add_node("hydrate_sources", self._hydrate_sources)
        graph.add_node("select_contexts", self._select_contexts)
        graph.add_node("generate_answer", self._generate_answer)
        graph.add_node("format_response", self._format_response)
        graph.add_edge(START, "embed_query")
        graph.add_edge("embed_query", "vector_search")
        graph.add_conditional_edges(
            "vector_search",
            self._next_after_search,
            {
                "hydrate_sources": "hydrate_sources",
                "format_response": "format_response",
            },
        )
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

    async def _embed_query(self, state: GlobalRagGraphState) -> GlobalRagGraphState:
        [query_vector] = await self._embeddings.embed([state["message"]])
        return {"query_vector": query_vector}

    async def _vector_search(self, state: GlobalRagGraphState) -> GlobalRagGraphState:
        groups = await self._vectors.search(
            query_vector=state["query_vector"],
            limit=max(self._similarity_top_k, state["limit"]),
            group_by="contractor_entity_id",
            group_size=_GROUP_SIZE,
        )
        search_groups = [group for group in groups if isinstance(group, SearchGroup)]
        return {"search_groups": search_groups}

    def _next_after_search(self, state: GlobalRagGraphState) -> str:
        if state.get("search_groups"):
            return "hydrate_sources"
        return "format_response"

    async def _hydrate_sources(
        self,
        state: GlobalRagGraphState,
    ) -> GlobalRagGraphState:
        search_groups = state["search_groups"]
        if not search_groups:
            return {"contractor_results": [], "contexts": []}

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
        contexts = sorted(
            contexts,
            key=lambda context: context.source.score,
            reverse=True,
        )
        return {
            "contractor_results": contractor_results,
            "contexts": contexts,
        }

    async def _select_contexts(
        self,
        state: GlobalRagGraphState,
    ) -> GlobalRagGraphState:
        selected_contexts = await select_contexts(
            query=state["message"],
            chunks=state.get("contexts", []),
            top_k=self._context_top_k,
            reranker=self._reranker,
        )
        return {"selected_contexts": selected_contexts}

    def _next_after_context_selection(self, state: GlobalRagGraphState) -> str:
        if state.get("selected_contexts"):
            return "generate_answer"
        return "format_response"

    async def _generate_answer(
        self,
        state: GlobalRagGraphState,
    ) -> GlobalRagGraphState:
        selected_contexts = state.get("selected_contexts", [])
        answer = await self._llm.complete(
            build_global_answer_messages(
                message=state["message"],
                contexts=selected_contexts,
                history=state["history"],
            ),
        )
        return {"answer_text": answer}

    async def _format_response(
        self,
        state: GlobalRagGraphState,
    ) -> GlobalRagGraphState:
        contractor_results = state.get("contractor_results", [])
        selected_contexts = state.get("selected_contexts", [])
        if not selected_contexts:
            response = GlobalRagAnswer(
                answer=NO_EVIDENCE_ANSWER,
                contractors=contractor_results[: state["limit"]],
                sources=[],
            )
        else:
            response = GlobalRagAnswer(
                answer=state.get("answer_text") or NO_EVIDENCE_ANSWER,
                contractors=contractor_results[: state["limit"]],
                sources=[context.source for context in selected_contexts],
            )
        return {"response": response}


def _contractor_id_from_group(group: SearchGroup) -> ContractorEntityId:
    return ContractorEntityId(UUID(group.group_key))


def _document_id_from_hit(hit: SearchHit) -> DocumentId | None:
    value = hit.payload.get("document_id")
    if value is None:
        return None
    return DocumentId(UUID(str(value)))


__all__ = ["AnswerGlobalSearchUseCase"]
