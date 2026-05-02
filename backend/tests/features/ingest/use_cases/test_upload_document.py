from collections.abc import MutableSequence
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

import pytest
from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.ingest.use_cases.upload_document import UploadDocumentUseCase


class FakeDocumentFileStorage:
    def __init__(
        self,
        calls: MutableSequence[str],
        *,
        raise_on_save: BaseException | None = None,
    ) -> None:
        self.calls = calls
        self.files: dict[Path, bytes] = {}
        self.raise_on_save = raise_on_save

    async def save(self, stream: BinaryIO, filename: str) -> Path:
        self.calls.append("save")
        if self.raise_on_save is not None:
            raise self.raise_on_save
        path = Path("/fake/uploads") / filename
        self.files[path] = stream.read()
        return path


class FakeDocumentRepository:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.documents: dict[DocumentId, Document] = {}

    async def add(self, document: Document) -> None:
        self.calls.append("add")
        self.documents[document.id] = document

    async def get(self, document_id: DocumentId) -> Document:
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

    async def set_error(self, document_id: DocumentId, message: str) -> None:
        raise NotImplementedError

    async def set_contractor_entity_id(
        self,
        document_id: DocumentId,
        contractor_entity_id: ContractorEntityId | None,
    ) -> None:
        raise NotImplementedError


class FakeIngestionTaskQueue:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.enqueued_processes: list[DocumentId] = []

    async def enqueue_process(self, document_id: DocumentId) -> None:
        assert "commit" in self.calls
        self.calls.append("enqueue")
        self.enqueued_processes.append(document_id)

    async def enqueue_resolve(self, document_id: DocumentId) -> None:
        raise NotImplementedError

    async def enqueue_index(self, document_id: DocumentId) -> None:
        raise NotImplementedError


class FakeUnitOfWork:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.committed = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        self.calls.append("enter")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.calls.append("exit")

    async def commit(self) -> None:
        self.calls.append("commit")
        self.committed = True

    async def rollback(self) -> None:
        self.calls.append("rollback")


async def test_upload_document_saves_document_commits_and_enqueues() -> None:
    calls: list[str] = []
    storage = FakeDocumentFileStorage(calls)
    documents = FakeDocumentRepository(calls)
    tasks = FakeIngestionTaskQueue(calls)
    uow = FakeUnitOfWork(calls)
    use_case = UploadDocumentUseCase(
        storage=storage,
        documents=documents,
        tasks=tasks,
        uow=uow,
    )

    document_id = await use_case.execute(
        file=BytesIO(b"contract contents"),
        filename="contract.pdf",
        content_type="application/pdf",
    )

    document = documents.documents[document_id]
    assert document.id == document_id
    assert document.title == "contract.pdf"
    assert document.file_path == "/fake/uploads/contract.pdf"
    assert document.content_type == "application/pdf"
    assert document.status == DocumentStatus.QUEUED
    assert document.error_message is None
    assert document.partial_extraction is False
    assert document.contractor_entity_id is None
    assert document.document_kind is None
    assert document.doc_type is None
    assert storage.files[Path("/fake/uploads/contract.pdf")] == b"contract contents"
    assert tasks.enqueued_processes == [document_id]
    assert uow.committed is True


async def test_upload_document_enqueues_only_after_commit() -> None:
    calls: list[str] = []
    use_case = UploadDocumentUseCase(
        storage=FakeDocumentFileStorage(calls),
        documents=FakeDocumentRepository(calls),
        tasks=FakeIngestionTaskQueue(calls),
        uow=FakeUnitOfWork(calls),
    )

    await use_case.execute(
        file=BytesIO(b"contract contents"),
        filename="contract.pdf",
        content_type="application/pdf",
    )

    ordered_calls = [
        call for call in calls if call in {"save", "add", "commit", "enqueue"}
    ]
    assert ordered_calls == [
        "save",
        "add",
        "commit",
        "enqueue",
    ]
    assert calls.index("commit") < calls.index("enqueue")


async def test_upload_document_does_not_persist_if_storage_raises() -> None:
    calls: list[str] = []
    documents = FakeDocumentRepository(calls)
    tasks = FakeIngestionTaskQueue(calls)
    uow = FakeUnitOfWork(calls)
    storage = FakeDocumentFileStorage(calls, raise_on_save=OSError("disk full"))
    use_case = UploadDocumentUseCase(
        storage=storage,
        documents=documents,
        tasks=tasks,
        uow=uow,
    )

    with pytest.raises(OSError, match="disk full"):
        await use_case.execute(
            file=BytesIO(b"contract contents"),
            filename="contract.pdf",
            content_type="application/pdf",
        )

    assert documents.documents == {}
    assert tasks.enqueued_processes == []
    assert uow.committed is False
