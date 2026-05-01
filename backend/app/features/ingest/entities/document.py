from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.core.domain.ids import ContractorEntityId, DocumentId


class DocumentStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RESOLVING = "RESOLVING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class InvalidStatusTransition(Exception):
    def __init__(
        self,
        current_status: DocumentStatus,
        target_status: DocumentStatus,
    ) -> None:
        super().__init__(
            "Invalid document status transition: "
            f"{current_status.value} -> {target_status.value}",
        )
        self.current_status = current_status
        self.target_status = target_status


@dataclass
class Document:
    id: DocumentId
    contractor_entity_id: ContractorEntityId | None
    title: str
    file_path: str
    content_type: str
    document_kind: str | None
    doc_type: str | None
    status: DocumentStatus
    error_message: str | None
    partial_extraction: bool
    created_at: datetime

    def __post_init__(self) -> None:
        self.status = DocumentStatus(self.status)

    def mark_processing(self) -> None:
        self._transition_to(
            DocumentStatus.PROCESSING,
            allowed_from={DocumentStatus.QUEUED},
        )

    def mark_resolving(self) -> None:
        self._transition_to(
            DocumentStatus.RESOLVING,
            allowed_from={DocumentStatus.PROCESSING},
        )

    def mark_indexing(self) -> None:
        self._transition_to(
            DocumentStatus.INDEXING,
            allowed_from={DocumentStatus.RESOLVING},
        )

    def mark_indexed(self) -> None:
        self._transition_to(
            DocumentStatus.INDEXED,
            allowed_from={DocumentStatus.INDEXING},
        )

    def mark_failed(self, message: str) -> None:
        self._transition_to(
            DocumentStatus.FAILED,
            allowed_from={
                DocumentStatus.QUEUED,
                DocumentStatus.PROCESSING,
                DocumentStatus.RESOLVING,
                DocumentStatus.INDEXING,
                DocumentStatus.FAILED,
            },
        )
        self.error_message = message

    def _transition_to(
        self,
        target_status: DocumentStatus,
        *,
        allowed_from: set[DocumentStatus],
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidStatusTransition(self.status, target_status)
        self.status = target_status


__all__ = ["Document", "DocumentStatus", "InvalidStatusTransition"]
