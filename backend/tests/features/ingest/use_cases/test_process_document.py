from collections.abc import MutableSequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from uuid import uuid4

import pytest
from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.ingest.use_cases.process_document import ProcessDocumentUseCase
from sage import Chunk, ContractFields, Page, ProcessingResult


class FakeDocumentRepository:
    def __init__(
        self,
        calls: MutableSequence[str],
        documents: dict[DocumentId, Document],
    ) -> None:
        self.calls = calls
        self.documents = documents
        self.status_updates: list[tuple[DocumentId, DocumentStatus]] = []
        self.processing_results: list[tuple[DocumentId, str, bool]] = []
        self.preview_paths: list[tuple[DocumentId, str | None]] = []
        self.errors: list[tuple[DocumentId, str]] = []

    async def get(self, document_id: DocumentId) -> Document:
        self.calls.append("documents.get")
        return self.documents[document_id]

    async def get_many(self, ids: list[DocumentId]) -> dict[DocumentId, Document]:
        raise NotImplementedError

    async def update_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
    ) -> None:
        self.calls.append(f"documents.update_status:{status.value}")
        self.documents[document_id].status = status
        self.status_updates.append((document_id, status))

    async def update_processing_result(
        self,
        document_id: DocumentId,
        *,
        document_kind: str,
        partial_extraction: bool,
    ) -> None:
        self.calls.append("documents.update_processing_result")
        document = self.documents[document_id]
        document.document_kind = document_kind
        document.partial_extraction = partial_extraction
        self.processing_results.append(
            (document_id, document_kind, partial_extraction),
        )

    async def set_preview_file_path(
        self,
        document_id: DocumentId,
        preview_file_path: str | None,
    ) -> None:
        self.calls.append("documents.set_preview_file_path")
        self.documents[document_id].preview_file_path = preview_file_path
        self.preview_paths.append((document_id, preview_file_path))

    async def set_error(self, document_id: DocumentId, message: str) -> None:
        self.calls.append("documents.set_error")
        document = self.documents[document_id]
        document.status = DocumentStatus.FAILED
        if document.error_message != message:
            document.error_message = message
        self.errors.append((document_id, message))

    async def add(self, document: Document) -> None:
        raise NotImplementedError

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        status: DocumentStatus | None = None,
        contractor_entity_id: ContractorEntityId | None = None,
    ) -> list[Document]:
        raise NotImplementedError

    async def set_contractor_entity_id(
        self,
        document_id: DocumentId,
        contractor_entity_id: ContractorEntityId | None,
    ) -> None:
        raise NotImplementedError


class FakeChunkRepository:
    def __init__(
        self,
        calls: MutableSequence[str],
        *,
        raise_on_add: BaseException | None = None,
    ) -> None:
        self.calls = calls
        self.raise_on_add = raise_on_add
        self.added: list[tuple[DocumentId, list[Chunk]]] = []

    async def add_many(self, document_id: DocumentId, chunks: list[Chunk]) -> None:
        self.calls.append("chunks.add_many")
        if self.raise_on_add is not None:
            raise self.raise_on_add
        self.added.append((document_id, chunks))

    async def list_for(self, document_id: DocumentId) -> list[Chunk]:
        raise NotImplementedError


class FakeFieldsRepository:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.upserts: list[tuple[DocumentId, ContractFields]] = []

    async def upsert(self, document_id: DocumentId, fields: ContractFields) -> None:
        self.calls.append("fields.upsert")
        self.upserts.append((document_id, fields))

    async def get(self, document_id: DocumentId) -> ContractFields | None:
        raise NotImplementedError


class FakeSummaryRepository:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.upserts: list[tuple[DocumentId, str, list[str]]] = []

    async def upsert(
        self,
        document_id: DocumentId,
        summary: str,
        key_points: list[str],
    ) -> None:
        self.calls.append("summaries.upsert")
        self.upserts.append((document_id, summary, key_points))

    async def get(self, document_id: DocumentId) -> tuple[str, list[str]] | None:
        raise NotImplementedError


class FakeSageProcessor:
    def __init__(
        self,
        calls: MutableSequence[str],
        *,
        result: ProcessingResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.calls = calls
        self.result = result
        self.error = error
        self.paths: list[Path] = []

    async def process(self, file_path: Path) -> ProcessingResult:
        self.calls.append("sage.process")
        self.paths.append(file_path)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


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


def _document(document_id: DocumentId) -> Document:
    return Document(
        id=document_id,
        contractor_entity_id=None,
        title="contract.pdf",
        file_path="/fake/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind=None,
        doc_type=None,
        status=DocumentStatus.QUEUED,
        error_message=None,
        partial_extraction=False,
        created_at=datetime.now(UTC),
    )


def _processing_result() -> ProcessingResult:
    return ProcessingResult(
        chunks=[
            Chunk(
                text="Contract chunk",
                page_start=1,
                page_end=1,
                section_type="body",
                chunk_index=0,
                chunk_summary="Chunk summary",
            ),
        ],
        fields=ContractFields(
            document_number="A-1",
            supplier_name="Test Contractor",
        ),
        summary="Document summary",
        pages=[Page(index=1, text="Contract chunk", kind="text")],
        document_kind="text",
        partial=False,
        preview_pdf_path="/fake/uploads/work/contract.pdf",
    )


def _use_case(
    *,
    calls: MutableSequence[str],
    documents: FakeDocumentRepository,
    chunks: FakeChunkRepository,
    fields: FakeFieldsRepository,
    summaries: FakeSummaryRepository,
    sage: FakeSageProcessor,
    uow: FakeUnitOfWork,
) -> ProcessDocumentUseCase:
    return ProcessDocumentUseCase(
        documents=documents,
        chunks=chunks,
        fields=fields,
        summaries=summaries,
        sage=sage,
        uow=uow,
    )


async def test_process_document_persists_sage_result_after_processing_commit() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    result = _processing_result()
    documents = FakeDocumentRepository(calls, {document_id: _document(document_id)})
    chunks = FakeChunkRepository(calls)
    fields = FakeFieldsRepository(calls)
    summaries = FakeSummaryRepository(calls)
    sage = FakeSageProcessor(calls, result=result)
    uow = FakeUnitOfWork(calls)
    use_case = _use_case(
        calls=calls,
        documents=documents,
        chunks=chunks,
        fields=fields,
        summaries=summaries,
        sage=sage,
        uow=uow,
    )

    await use_case.execute(document_id)

    document = documents.documents[document_id]
    assert document.status == DocumentStatus.PROCESSING
    assert document.document_kind == "text"
    assert document.partial_extraction is False
    assert document.preview_file_path == "/fake/uploads/work/contract.pdf"
    assert documents.status_updates == [(document_id, DocumentStatus.PROCESSING)]
    assert documents.processing_results == [(document_id, "text", False)]
    assert documents.preview_paths == [
        (document_id, "/fake/uploads/work/contract.pdf"),
    ]
    assert chunks.added == [(document_id, result.chunks)]
    assert fields.upserts == [(document_id, result.fields)]
    assert summaries.upserts == [(document_id, "Document summary", [])]
    assert sage.paths == [Path("/fake/uploads/contract.pdf")]
    assert uow.commits == 2

    assert calls.index("uow.commit:1") < calls.index("sage.process")
    assert calls.index("sage.process") < calls.index("uow.enter", 1)
    assert calls.index("chunks.add_many") < calls.index("uow.commit:2")
    assert "enqueue_resolve" not in calls


async def test_process_document_marks_failed_and_reraises_when_sage_fails() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository(calls, {document_id: _document(document_id)})
    chunks = FakeChunkRepository(calls)
    fields = FakeFieldsRepository(calls)
    summaries = FakeSummaryRepository(calls)
    sage = FakeSageProcessor(calls, error=RuntimeError("sage failed"))
    uow = FakeUnitOfWork(calls)
    use_case = _use_case(
        calls=calls,
        documents=documents,
        chunks=chunks,
        fields=fields,
        summaries=summaries,
        sage=sage,
        uow=uow,
    )

    with pytest.raises(RuntimeError, match="sage failed"):
        await use_case.execute(document_id)

    document = documents.documents[document_id]
    assert document.status == DocumentStatus.FAILED
    assert document.error_message == "sage failed"
    assert documents.errors == [(document_id, "sage failed")]
    assert chunks.added == []
    assert fields.upserts == []
    assert summaries.upserts == []
    assert uow.commits == 2
    assert calls.count("uow.enter") == 2
    assert calls.index("sage.process") < calls.index("documents.set_error")


async def test_process_document_marks_failed_when_persisting_fails() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    documents = FakeDocumentRepository(calls, {document_id: _document(document_id)})
    chunks = FakeChunkRepository(calls, raise_on_add=RuntimeError("chunks failed"))
    fields = FakeFieldsRepository(calls)
    summaries = FakeSummaryRepository(calls)
    sage = FakeSageProcessor(calls, result=_processing_result())
    uow = FakeUnitOfWork(calls)
    use_case = _use_case(
        calls=calls,
        documents=documents,
        chunks=chunks,
        fields=fields,
        summaries=summaries,
        sage=sage,
        uow=uow,
    )

    with pytest.raises(RuntimeError, match="chunks failed"):
        await use_case.execute(document_id)

    document = documents.documents[document_id]
    assert document.status == DocumentStatus.FAILED
    assert document.error_message == "chunks failed"
    assert documents.errors == [(document_id, "chunks failed")]
    assert fields.upserts == []
    assert summaries.upserts == []
    assert documents.processing_results == []
    assert uow.commits == 2
    assert calls.count("uow.enter") == 3
    assert calls.index("chunks.add_many") < calls.index("documents.set_error")
