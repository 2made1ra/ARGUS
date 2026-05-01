from dataclasses import dataclass
from datetime import datetime

from app.core.domain.ids import ContractorEntityId, DocumentId


@dataclass
class Document:
    # TODO: Track 4 will extend this stub with lifecycle behavior and DocumentStatus.
    id: DocumentId
    contractor_entity_id: ContractorEntityId | None
    title: str | None
    file_path: str | None
    content_type: str | None
    document_kind: str | None
    doc_type: str | None
    status: str | None
    error_message: str | None
    partial_extraction: bool | None
    created_at: datetime | None


__all__ = ["Document"]
