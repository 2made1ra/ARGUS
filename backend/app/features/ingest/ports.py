from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol, runtime_checkable
from uuid import UUID

from sage import Chunk, ContractFields, ProcessingResult

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.entities.document import Document, DocumentStatus


class DocumentNotFound(Exception):
    def __init__(self, document_id: DocumentId) -> None:
        super().__init__(f"Document not found: {document_id}")
        self.document_id = document_id


@dataclass
class VectorPoint:
    id: UUID
    vector: list[float]
    payload: dict[str, Any]


@runtime_checkable
class DocumentRepository(Protocol):
    async def add(self, document: Document) -> None: ...

    async def get(self, document_id: DocumentId) -> Document: ...

    async def list(self, *, limit: int, offset: int) -> list[Document]: ...

    async def update_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
    ) -> None: ...

    async def update_processing_result(
        self,
        document_id: DocumentId,
        *,
        document_kind: str,
        partial_extraction: bool,
    ) -> None: ...

    async def set_error(self, document_id: DocumentId, message: str) -> None: ...

    async def set_contractor_entity_id(
        self,
        document_id: DocumentId,
        contractor_entity_id: ContractorEntityId | None,
    ) -> None: ...


@runtime_checkable
class ChunkRepository(Protocol):
    async def add_many(self, document_id: DocumentId, chunks: list[Chunk]) -> None: ...

    async def list_for(self, document_id: DocumentId) -> list[Chunk]: ...


@runtime_checkable
class FieldsRepository(Protocol):
    async def upsert(self, document_id: DocumentId, fields: ContractFields) -> None: ...

    async def get(self, document_id: DocumentId) -> ContractFields | None: ...


@runtime_checkable
class SummaryRepository(Protocol):
    async def upsert(
        self,
        document_id: DocumentId,
        summary: str,
        key_points: list[str],
    ) -> None: ...

    async def get(self, document_id: DocumentId) -> tuple[str, list[str]] | None: ...


@runtime_checkable
class DocumentFileStorage(Protocol):
    async def save(self, stream: BinaryIO, filename: str) -> Path: ...


@runtime_checkable
class SageProcessor(Protocol):
    async def process(self, file_path: Path) -> ProcessingResult: ...


@runtime_checkable
class IngestionTaskQueue(Protocol):
    async def enqueue_process(self, document_id: DocumentId) -> None: ...

    async def enqueue_resolve(self, document_id: DocumentId) -> None: ...

    async def enqueue_index(self, document_id: DocumentId) -> None: ...


@runtime_checkable
class EmbeddingService(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class VectorIndex(Protocol):
    async def upsert_chunks(self, points: list[VectorPoint]) -> None: ...

    async def delete_document(self, document_id: DocumentId) -> None: ...


__all__ = [
    "Chunk",
    "ChunkRepository",
    "ContractFields",
    "DocumentFileStorage",
    "DocumentNotFound",
    "DocumentRepository",
    "EmbeddingService",
    "FieldsRepository",
    "IngestionTaskQueue",
    "ProcessingResult",
    "SageProcessor",
    "SummaryRepository",
    "VectorIndex",
    "VectorPoint",
]
