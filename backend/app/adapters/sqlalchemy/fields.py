from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sage import ContractFields

from app.adapters.sqlalchemy.models import ExtractedField
from app.core.domain.ids import DocumentId


class SqlAlchemyFieldsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, document_id: DocumentId, fields: ContractFields) -> None:
        statement = insert(ExtractedField).values(
            id=uuid4(),
            document_id=document_id,
            fields=fields.model_dump(),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[ExtractedField.document_id],
            set_={"fields": statement.excluded.fields},
        )
        await self._session.execute(statement)

    async def get(self, document_id: DocumentId) -> ContractFields | None:
        statement = select(ExtractedField.fields).where(
            ExtractedField.document_id == document_id,
        )
        data = await self._session.scalar(statement)
        if data is None:
            return None
        return ContractFields(**data)


__all__ = ["SqlAlchemyFieldsRepository"]
