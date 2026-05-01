from collections.abc import MutableSequence
from datetime import UTC, datetime
from types import TracebackType
from uuid import NAMESPACE_OID, uuid4, uuid5

import pytest
from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.contractors.entities.contractor import Contractor
from app.features.ingest.chunk_ids import stable_chunk_id, stable_summary_id
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.ingest.ports import VectorPoint
from app.features.ingest.use_cases.index_document import IndexDocumentUseCase
from sage import Chunk, ContractFields


class FakeDocumentRepository:
    def __init__(
        self,
        calls: MutableSequence[str],
        documents: dict[DocumentId, Document],
    ) -> None:
        self.calls = calls
        self.documents = documents
        self.status_updates: list[tuple[DocumentId, DocumentStatus]] = []
        self.errors: list[tuple[DocumentId, str]] = []

    async def get(self, document_id: DocumentId) -> Document:
        self.calls.append("documents.get")
        return self.documents[document_id]

    async def update_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
    ) -> None:
        self.calls.append(f"documents.update_status:{status.value}")
        self.documents[document_id].status = status
        self.status_updates.append((document_id, status))

    async def set_error(self, document_id: DocumentId, message: str) -> None:
        self.calls.append("documents.set_error")
        document = self.documents[document_id]
        document.status = DocumentStatus.FAILED
        document.error_message = message
        self.errors.append((document_id, message))


class FakeChunkRepository:
    def __init__(self, calls: MutableSequence[str], chunks: list[Chunk]) -> None:
        self.calls = calls
        self.chunks = chunks

    async def list_for(self, document_id: DocumentId) -> list[Chunk]:
        self.calls.append("chunks.list_for")
        return self.chunks


class FakeFieldsRepository:
    def __init__(
        self,
        calls: MutableSequence[str],
        fields: ContractFields | None,
    ) -> None:
        self.calls = calls
        self.fields = fields

    async def get(self, document_id: DocumentId) -> ContractFields | None:
        self.calls.append("fields.get")
        return self.fields


class FakeSummaryRepository:
    def __init__(
        self,
        calls: MutableSequence[str],
        summary: tuple[str, list[str]] | None,
    ) -> None:
        self.calls = calls
        self.summary = summary

    async def get(self, document_id: DocumentId) -> tuple[str, list[str]] | None:
        self.calls.append("summaries.get")
        return self.summary


class FakeContractorRepository:
    def __init__(
        self,
        calls: MutableSequence[str],
        contractors: dict[ContractorEntityId, Contractor],
    ) -> None:
        self.calls = calls
        self.contractors = contractors
        self.gets: list[ContractorEntityId] = []

    async def get(self, id: ContractorEntityId) -> Contractor:
        self.calls.append("contractors.get")
        self.gets.append(id)
        return self.contractors[id]


class FakeEmbeddingService:
    def __init__(
        self,
        calls: MutableSequence[str],
        *,
        error: BaseException | None = None,
    ) -> None:
        self.calls = calls
        self.error = error
        self.texts: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append("embeddings.embed")
        self.texts.append(texts)
        if self.error is not None:
            raise self.error
        return [[float(index), 1.0] for index, _text in enumerate(texts)]


class FakeVectorIndex:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.upserts: list[list[VectorPoint]] = []

    async def upsert_chunks(self, points: list[VectorPoint]) -> None:
        self.calls.append("index.upsert_chunks")
        self.upserts.append(points)


class FakeUnitOfWork:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.commits = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        self.calls.append("uow.enter")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.calls.append("uow.exit")

    async def commit(self) -> None:
        self.commits += 1
        self.calls.append(f"uow.commit:{self.commits}")

    async def rollback(self) -> None:
        self.calls.append("uow.rollback")


def _document(
    document_id: DocumentId,
    contractor_entity_id: ContractorEntityId | None,
) -> Document:
    return Document(
        id=document_id,
        contractor_entity_id=contractor_entity_id,
        title="contract.pdf",
        file_path="/fake/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind="text",
        doc_type="contract",
        status=DocumentStatus.RESOLVING,
        error_message=None,
        partial_extraction=False,
        created_at=datetime.now(UTC),
    )


def _contractor(contractor_id: ContractorEntityId) -> Contractor:
    return Contractor(
        id=contractor_id,
        display_name="ООО Вектор",
        normalized_key="вектор",
        inn="7701234567",
        kpp=None,
        created_at=datetime.now(UTC),
    )


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            text="First chunk",
            page_start=1,
            page_end=1,
            section_type="header",
            chunk_index=0,
            chunk_summary="First",
        ),
        Chunk(
            text="x" * 8100,
            page_start=2,
            page_end=3,
            section_type="body",
            chunk_index=1,
            chunk_summary="Second",
        ),
        Chunk(
            text="Third chunk",
            page_start=4,
            page_end=4,
            section_type=None,
            chunk_index=2,
            chunk_summary=None,
        ),
    ]


def _use_case(
    *,
    calls: MutableSequence[str],
    documents: FakeDocumentRepository,
    chunks: FakeChunkRepository,
    fields: FakeFieldsRepository,
    summaries: FakeSummaryRepository,
    contractors: FakeContractorRepository,
    embeddings: FakeEmbeddingService,
    index: FakeVectorIndex,
    uow: FakeUnitOfWork,
) -> IndexDocumentUseCase:
    return IndexDocumentUseCase(
        documents=documents,
        chunks=chunks,
        fields=fields,
        summaries=summaries,
        contractors=contractors,
        embeddings=embeddings,
        index=index,
        uow=uow,
    )


@pytest.mark.asyncio
async def test_index_document_embeds_chunks_and_summary_in_one_batch() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    contractor_id = ContractorEntityId(uuid4())
    chunk_rows = _chunks()
    documents = FakeDocumentRepository(
        calls,
        {document_id: _document(document_id, contractor_id)},
    )
    chunks = FakeChunkRepository(calls, chunk_rows)
    fields = FakeFieldsRepository(
        calls,
        ContractFields(document_date="2025-01-15"),
    )
    summaries = FakeSummaryRepository(calls, ("s" * 8100, ["key point"]))
    contractors = FakeContractorRepository(
        calls,
        {contractor_id: _contractor(contractor_id)},
    )
    embeddings = FakeEmbeddingService(calls)
    index = FakeVectorIndex(calls)
    uow = FakeUnitOfWork(calls)
    use_case = _use_case(
        calls=calls,
        documents=documents,
        chunks=chunks,
        fields=fields,
        summaries=summaries,
        contractors=contractors,
        embeddings=embeddings,
        index=index,
        uow=uow,
    )

    await use_case.execute(document_id)

    document = documents.documents[document_id]
    assert document.status == DocumentStatus.INDEXED
    assert documents.status_updates == [
        (document_id, DocumentStatus.INDEXING),
        (document_id, DocumentStatus.INDEXED),
    ]
    assert contractors.gets == [contractor_id]
    assert len(embeddings.texts) == 1
    assert len(index.upserts) == 1

    points = index.upserts[0]
    assert len(points) == 4
    assert embeddings.texts == [
        ["First chunk", "x" * 8000, "Third chunk", "s" * 8000],
    ]
    assert [point.vector for point in points] == [
        [0.0, 1.0],
        [1.0, 1.0],
        [2.0, 1.0],
        [3.0, 1.0],
    ]

    first_payload = points[0].payload
    assert points[0].id == stable_chunk_id(document_id, 0)
    assert points[0].id == uuid5(NAMESPACE_OID, f"{document_id}:0")
    assert first_payload == {
        "document_id": str(document_id),
        "contractor_entity_id": str(contractor_id),
        "doc_type": "contract",
        "document_kind": "text",
        "date": "2025-01-15",
        "page_start": 1,
        "page_end": 1,
        "section_type": "header",
        "chunk_index": 0,
        "text": "First chunk",
        "is_summary": False,
    }
    assert points[1].payload["text"] == "x" * 8000
    assert points[2].payload["section_type"] is None

    summary = points[3]
    assert summary.id == stable_summary_id(document_id)
    assert summary.payload["chunk_index"] == -1
    assert summary.payload["is_summary"] is True
    assert summary.payload["page_start"] is None
    assert summary.payload["page_end"] is None
    assert summary.payload["text"] == "s" * 8000

    assert uow.commits == 2
    assert calls.index("uow.commit:1") < calls.index("chunks.list_for")
    assert calls.index("embeddings.embed") < calls.index("index.upsert_chunks")
    assert calls.index("index.upsert_chunks") < calls.index(
        "documents.update_status:INDEXED",
    )


@pytest.mark.asyncio
async def test_index_document_marks_failed_and_reraises_when_embed_fails() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository(
        calls,
        {document_id: _document(document_id, None)},
    )
    chunks = FakeChunkRepository(calls, _chunks())
    fields = FakeFieldsRepository(calls, ContractFields(document_date="2025-01-15"))
    summaries = FakeSummaryRepository(calls, ("Document summary", []))
    contractors = FakeContractorRepository(calls, {})
    embeddings = FakeEmbeddingService(calls, error=RuntimeError("embed failed"))
    index = FakeVectorIndex(calls)
    uow = FakeUnitOfWork(calls)
    use_case = _use_case(
        calls=calls,
        documents=documents,
        chunks=chunks,
        fields=fields,
        summaries=summaries,
        contractors=contractors,
        embeddings=embeddings,
        index=index,
        uow=uow,
    )

    with pytest.raises(RuntimeError, match="embed failed"):
        await use_case.execute(document_id)

    document = documents.documents[document_id]
    assert document.status == DocumentStatus.FAILED
    assert document.error_message == "embed failed"
    assert documents.status_updates == [(document_id, DocumentStatus.INDEXING)]
    assert documents.errors == [(document_id, "embed failed")]
    assert len(embeddings.texts) == 1
    assert index.upserts == []
    assert uow.commits == 2
    assert calls.index("embeddings.embed") < calls.index("documents.set_error")
