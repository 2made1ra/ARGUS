from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

CatalogImportJobStatus = Literal[
    "QUEUED",
    "IMPORTING",
    "INDEXING",
    "COMPLETED",
    "FAILED",
]
CatalogImportJobStage = Literal["upload", "import", "indexing", "completed", "failed"]


@dataclass(slots=True)
class CatalogImportJob:
    id: UUID
    filename: str
    source_path: str
    file_size_bytes: int
    status: CatalogImportJobStatus
    stage: CatalogImportJobStage
    progress_percent: int
    stage_progress_percent: int
    row_count: int
    valid_row_count: int
    invalid_row_count: int
    index_total: int
    indexed: int
    embedding_failed: int
    indexing_failed: int
    skipped: int
    import_batch_id: UUID | None
    source_file_id: UUID | None
    error_message: str | None
    created_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None


__all__ = [
    "CatalogImportJob",
    "CatalogImportJobStage",
    "CatalogImportJobStatus",
]
