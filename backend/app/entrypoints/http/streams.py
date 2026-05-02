from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.sqlalchemy.documents import SqlAlchemyDocumentRepository
from app.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from app.core.domain.ids import DocumentId
from app.entrypoints.http.dependencies import get_sessionmaker
from app.features.ingest.entities.document import Document, DocumentStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_TERMINAL = frozenset({DocumentStatus.INDEXED, DocumentStatus.FAILED})

# Callable that fetches a fresh document snapshot; hides the UoW lifecycle.
type _Repo = Callable[[DocumentId], Coroutine[Any, Any, Document]]


async def _status_stream(
    document_id: DocumentId,
    repo: _Repo,
) -> AsyncIterator[str]:
    """Poll document status every ~1 s, yield SSE events on transitions."""
    last_status: DocumentStatus | None = None

    while True:
        try:
            doc = await repo(document_id)
        except Exception:
            logger.exception("SSE poll failed for %s; retrying in 1 s", document_id)
            await asyncio.sleep(1)
            continue

        if doc.status != last_status:
            last_status = doc.status
            payload: dict[str, Any] = {
                "status": doc.status,
                "document_id": str(document_id),
            }
            if doc.status == DocumentStatus.FAILED:
                payload["error_message"] = doc.error_message
            yield f"data: {json.dumps(payload)}\n\n"

        if doc.status in _TERMINAL:
            break

        await asyncio.sleep(1)


@router.get("/{id}/stream")
async def stream_document_status(
    id: UUID,
    sm: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
) -> StreamingResponse:
    doc_id = DocumentId(id)

    async def _fetch(document_id: DocumentId) -> Document:
        async with SqlAlchemyUnitOfWork(sm) as uow:
            return await SqlAlchemyDocumentRepository(uow.session).get(document_id)

    return StreamingResponse(
        _status_stream(doc_id, _fetch),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
