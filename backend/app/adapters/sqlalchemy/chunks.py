from sage import Chunk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import DocumentChunk
from app.core.domain.ids import DocumentId
from app.features.ingest.chunk_ids import stable_chunk_id


class SqlAlchemyChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, document_id: DocumentId, chunks: list[Chunk]) -> None:
        self._session.add_all(
            [
                DocumentChunk(
                    id=stable_chunk_id(document_id, chunk.chunk_index),
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_type=chunk.section_type,
                    chunk_summary=chunk.chunk_summary,
                )
                for chunk in chunks
            ],
        )

    async def list_for(self, document_id: DocumentId) -> list[Chunk]:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        rows = await self._session.scalars(statement)
        return [
            Chunk(
                text=row.text or "",
                page_start=row.page_start or 0,
                page_end=row.page_end or 0,
                section_type=row.section_type,
                chunk_index=row.chunk_index or 0,
                chunk_summary=row.chunk_summary,
            )
            for row in rows
        ]


__all__ = ["SqlAlchemyChunkRepository"]
