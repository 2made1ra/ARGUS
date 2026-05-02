from __future__ import annotations

from pathlib import Path

from app.core.domain.ids import DocumentId
from app.features.documents.dto import (
    DocumentPreviewDTO,
    DocumentPreviewUnavailable,
)
from app.features.ingest.ports import DocumentRepository


class GetDocumentPreviewUseCase:
    def __init__(self, *, documents: DocumentRepository) -> None:
        self._documents = documents

    async def execute(self, document_id: DocumentId) -> DocumentPreviewDTO:
        document = await self._documents.get(document_id)
        path = _preview_path(document.preview_file_path, document.file_path)
        if path is None or not path.exists():
            raise DocumentPreviewUnavailable(document_id)
        return DocumentPreviewDTO(path=path, media_type="application/pdf")


def _preview_path(preview_file_path: str | None, file_path: str) -> Path | None:
    if preview_file_path:
        return Path(preview_file_path)
    if file_path.lower().endswith(".pdf"):
        return Path(file_path)
    return None


__all__ = ["GetDocumentPreviewUseCase"]
