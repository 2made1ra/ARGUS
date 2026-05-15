from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.contractors.entities.contractor import Contractor
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.search.dto import ChatMessage, SearchGroup, SearchHit
from app.features.search.use_cases.answer_contractor import AnswerContractorUseCase
from app.features.search.use_cases.answer_document import AnswerDocumentUseCase
from app.features.search.use_cases.answer_global import AnswerGlobalSearchUseCase
from sage import ContractFields


class FakeEmbeddingService:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeVectorSearch:
    def __init__(self, results: list[SearchHit] | list[SearchGroup]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        *,
        query_vector: list[float],
        limit: int,
        filter: dict[str, Any] | None = None,
        group_by: str | None = None,
        group_size: int = 3,
    ) -> list[SearchHit] | list[SearchGroup]:
        self.calls.append(
            {
                "query_vector": query_vector,
                "limit": limit,
                "filter": filter,
                "group_by": group_by,
                "group_size": group_size,
            },
        )
        return self.results


class FakeLLM:
    def __init__(self, answer: str = "Найден подходящий подрядчик [S1].") -> None:
        self.answer = answer
        self.calls: list[list[ChatMessage]] = []

    async def complete(self, messages: list[ChatMessage]) -> str:
        self.calls.append(messages)
        return self.answer


class FakeContractorRepository:
    def __init__(self, contractors: dict[ContractorEntityId, Contractor]) -> None:
        self.contractors = contractors

    async def get(self, id: ContractorEntityId) -> Contractor:
        return self.contractors[id]

    async def get_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, Contractor]:
        return {id: self.contractors[id] for id in ids if id in self.contractors}

    async def count_documents_for(self, id: ContractorEntityId) -> int:
        return 2

    async def count_documents_for_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, int]:
        return {id: 2 for id in ids}

    async def add(self, contractor: Contractor) -> None:
        raise NotImplementedError

    async def find_by_inn(self, inn: str) -> Contractor | None:
        raise NotImplementedError

    async def find_by_normalized_key(self, key: str) -> Contractor | None:
        raise NotImplementedError

    async def find_all_for_fuzzy(self) -> list[Contractor]:
        raise NotImplementedError

    async def list_for_contractor(
        self,
        id: ContractorEntityId,
        *,
        limit: int,
        offset: int,
    ) -> list[Document]:
        raise NotImplementedError

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        q: str | None = None,
    ) -> list[Contractor]:
        raise NotImplementedError


class FakeDocumentRepository:
    def __init__(self, documents: dict[DocumentId, Document]) -> None:
        self.documents = documents

    async def add(self, document: Document) -> None:
        raise NotImplementedError

    async def get(self, document_id: DocumentId) -> Document:
        return self.documents[document_id]

    async def get_many(self, ids: list[DocumentId]) -> dict[DocumentId, Document]:
        return {id: self.documents[id] for id in ids if id in self.documents}

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        status: DocumentStatus | None = None,
        contractor_entity_id: ContractorEntityId | None = None,
    ) -> list[Document]:
        raise NotImplementedError

    async def update_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
    ) -> None:
        raise NotImplementedError

    async def update_processing_result(
        self,
        document_id: DocumentId,
        *,
        document_kind: str,
        partial_extraction: bool,
    ) -> None:
        raise NotImplementedError

    async def set_preview_file_path(
        self,
        document_id: DocumentId,
        preview_file_path: str | None,
    ) -> None:
        raise NotImplementedError

    async def set_error(self, document_id: DocumentId, message: str) -> None:
        raise NotImplementedError

    async def set_contractor_entity_id(
        self,
        document_id: DocumentId,
        contractor_entity_id: ContractorEntityId | None,
    ) -> None:
        raise NotImplementedError


class FakeFieldsRepository:
    async def upsert(self, document_id: DocumentId, fields: ContractFields) -> None:
        raise NotImplementedError

    async def get(self, document_id: DocumentId) -> ContractFields | None:
        return ContractFields(service_subject="поставка фруктов")


class FakeSummaryRepository:
    async def upsert(
        self,
        document_id: DocumentId,
        summary: str,
        key_points: list[str],
    ) -> None:
        raise NotImplementedError

    async def get(self, document_id: DocumentId) -> tuple[str, list[str]] | None:
        return ("Договор на поставку фруктов.", [])


@pytest.mark.asyncio
async def test_global_rag_answer_groups_contractors_and_returns_sources() -> None:
    contractor_id = ContractorEntityId(uuid4())
    document_id = DocumentId(uuid4())
    hit = _hit(
        document_id=document_id,
        contractor_id=contractor_id,
        score=0.92,
        text="ООО ФруктТорг поставляет фрукты по договору.",
    )
    vectors = FakeVectorSearch([SearchGroup(group_key=str(contractor_id), hits=[hit])])
    llm = FakeLLM()
    use_case = AnswerGlobalSearchUseCase(
        embeddings=FakeEmbeddingService(),
        vectors=vectors,
        contractors=FakeContractorRepository(
            {contractor_id: _contractor(contractor_id, "ООО ФруктТорг")},
        ),
        documents=FakeDocumentRepository(
            {document_id: _document(document_id, contractor_id, "Договор поставки")},
        ),
        llm=llm,
        similarity_top_k=15,
        context_top_k=5,
    )

    assert use_case._graph.__class__.__name__ == "CompiledStateGraph"

    answer = await use_case.execute(
        message="мне нужны поставщики фруктов",
        history=[],
    )

    assert answer.answer == "Найден подходящий подрядчик [S1]."
    assert answer.contractors[0].name == "ООО ФруктТорг"
    assert answer.contractors[0].document_count == 2
    assert answer.sources[0].document_id == document_id
    assert answer.sources[0].contractor_name == "ООО ФруктТорг"
    assert llm.calls
    assert "только по предоставленному контексту" in llm.calls[0][0].content


@pytest.mark.asyncio
async def test_contractor_rag_answer_returns_no_evidence_without_hits() -> None:
    contractor_id = ContractorEntityId(uuid4())
    llm = FakeLLM()
    use_case = AnswerContractorUseCase(
        embeddings=FakeEmbeddingService(),
        vectors=FakeVectorSearch([]),
        contractors=FakeContractorRepository(
            {contractor_id: _contractor(contractor_id, "ООО ФруктТорг")},
        ),
        documents=FakeDocumentRepository({}),
        llm=llm,
    )

    assert use_case._graph.__class__.__name__ == "CompiledStateGraph"

    answer = await use_case.execute(
        contractor_id=contractor_id,
        message="что известно о штрафах",
        history=[],
    )

    assert "недостаточно данных" in answer.answer
    assert answer.sources == []
    assert llm.calls == []


@pytest.mark.asyncio
async def test_document_rag_answer_uses_document_scope_and_sources() -> None:
    contractor_id = ContractorEntityId(uuid4())
    document_id = DocumentId(uuid4())
    hit = _hit(
        document_id=document_id,
        contractor_id=contractor_id,
        score=0.88,
        text="Предмет договора — поставка фруктов.",
    )
    vectors = FakeVectorSearch([hit])
    llm = FakeLLM("По договору поставляются фрукты [S1].")
    use_case = AnswerDocumentUseCase(
        embeddings=FakeEmbeddingService(),
        vectors=vectors,
        documents=FakeDocumentRepository(
            {document_id: _document(document_id, contractor_id, "Договор поставки")},
        ),
        fields=FakeFieldsRepository(),
        summaries=FakeSummaryRepository(),
        llm=llm,
    )

    assert use_case._graph.__class__.__name__ == "CompiledStateGraph"

    answer = await use_case.execute(
        document_id=document_id,
        message="дай summary договора",
        history=[],
    )

    assert answer.answer == "По договору поставляются фрукты [S1]."
    assert answer.sources[0].document_id == document_id
    assert vectors.calls[0]["filter"] == {
        "must": [{"key": "document_id", "match": {"value": str(document_id)}}],
    }


def _hit(
    *,
    document_id: DocumentId,
    contractor_id: ContractorEntityId,
    score: float,
    text: str,
) -> SearchHit:
    return SearchHit(
        id=UUID(str(uuid4())),
        score=score,
        payload={
            "document_id": str(document_id),
            "contractor_entity_id": str(contractor_id),
            "page_start": 1,
            "page_end": 1,
            "chunk_index": 0,
            "text": text,
        },
    )


def _contractor(id: ContractorEntityId, name: str) -> Contractor:
    return Contractor(
        id=id,
        display_name=name,
        normalized_key=name.casefold(),
        inn="1234567890",
        kpp=None,
        created_at=datetime.now(UTC),
    )


def _document(
    id: DocumentId,
    contractor_id: ContractorEntityId,
    title: str,
) -> Document:
    return Document(
        id=id,
        contractor_entity_id=contractor_id,
        title=title,
        file_path="/tmp/contract.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type="contract",
        status=DocumentStatus.INDEXED,
        error_message=None,
        partial_extraction=False,
        created_at=datetime.now(UTC),
    )
