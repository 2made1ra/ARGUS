from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import DocumentSummary
from app.core.domain.ids import DocumentId


class SqlAlchemySummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        document_id: DocumentId,
        summary: str,
        key_points: list[str],
    ) -> None:
        statement = insert(DocumentSummary).values(
            id=uuid4(),
            document_id=document_id,
            summary=summary,
            key_points=key_points,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[DocumentSummary.document_id],
            set_={
                "summary": statement.excluded.summary,
                "key_points": statement.excluded.key_points,
            },
        )
        await self._session.execute(statement)

    async def get(self, document_id: DocumentId) -> tuple[str, list[str]] | None:
        statement = select(
            DocumentSummary.summary,
            DocumentSummary.key_points,
        ).where(DocumentSummary.document_id == document_id)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        summary, key_points = row
        return summary or "", key_points or []


__all__ = ["SqlAlchemySummaryRepository"]
