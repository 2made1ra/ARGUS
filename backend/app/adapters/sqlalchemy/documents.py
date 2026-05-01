from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import Document as DocumentRow
from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.entities.document import Document
from app.features.ingest.ports import DocumentNotFound


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> None:
        statement = insert(DocumentRow).values(
            id=document.id,
            contractor_entity_id=document.contractor_entity_id,
            title=document.title,
            file_path=document.file_path,
            content_type=document.content_type,
            document_kind=document.document_kind,
            doc_type=document.doc_type,
            status=document.status,
            error_message=document.error_message,
            partial_extraction=document.partial_extraction,
            # created_at omitted — filled by server default (func.now())
        )
        await self._session.execute(statement)

    async def get(self, document_id: DocumentId) -> Document:
        statement = select(DocumentRow).where(DocumentRow.id == document_id)
        row = await self._session.scalar(statement)
        if row is None:
            raise DocumentNotFound(document_id)
        return _to_entity(row)

    async def list(self, *, limit: int, offset: int) -> list[Document]:
        statement = (
            select(DocumentRow)
            .order_by(DocumentRow.created_at.desc(), DocumentRow.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.scalars(statement)
        return [_to_entity(row) for row in rows]

    async def update_status(self, document_id: DocumentId, status: str) -> None:
        statement = (
            update(DocumentRow)
            .where(DocumentRow.id == document_id)
            .values(status=status)
            .returning(DocumentRow.id)
        )
        result = await self._session.execute(statement)
        if result.scalar_one_or_none() is None:
            raise DocumentNotFound(document_id)

    async def set_error(self, document_id: DocumentId, message: str) -> None:
        statement = (
            update(DocumentRow)
            .where(DocumentRow.id == document_id)
            .values(status="FAILED", error_message=message)
            .returning(DocumentRow.id)
        )
        result = await self._session.execute(statement)
        if result.scalar_one_or_none() is None:
            raise DocumentNotFound(document_id)


def _to_entity(row: DocumentRow) -> Document:
    contractor_entity_id = (
        ContractorEntityId(row.contractor_entity_id)
        if row.contractor_entity_id is not None
        else None
    )
    return Document(
        id=DocumentId(row.id),
        contractor_entity_id=contractor_entity_id,
        title=row.title,
        file_path=row.file_path,
        content_type=row.content_type,
        document_kind=row.document_kind,
        doc_type=row.doc_type,
        status=row.status,
        error_message=row.error_message,
        partial_extraction=row.partial_extraction,
        created_at=row.created_at,
    )


__all__ = ["SqlAlchemyDocumentRepository"]
