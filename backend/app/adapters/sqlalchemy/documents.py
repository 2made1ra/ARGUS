from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import Document as DocumentRow
from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.entities.document import Document, DocumentStatus
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

    async def update_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
    ) -> None:
        statement = (
            update(DocumentRow)
            .where(DocumentRow.id == document_id)
            .values(status=status)
            .returning(DocumentRow.id)
        )
        result = await self._session.execute(statement)
        if result.scalar_one_or_none() is None:
            raise DocumentNotFound(document_id)

    async def update_processing_result(
        self,
        document_id: DocumentId,
        *,
        document_kind: str,
        partial_extraction: bool,
    ) -> None:
        statement = (
            update(DocumentRow)
            .where(DocumentRow.id == document_id)
            .values(
                document_kind=document_kind,
                partial_extraction=partial_extraction,
            )
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

    async def set_contractor_entity_id(
        self,
        document_id: DocumentId,
        contractor_entity_id: ContractorEntityId | None,
    ) -> None:
        statement = (
            update(DocumentRow)
            .where(DocumentRow.id == document_id)
            .values(contractor_entity_id=contractor_entity_id)
            .returning(DocumentRow.id)
        )
        result = await self._session.execute(statement)
        if result.scalar_one_or_none() is None:
            raise DocumentNotFound(document_id)


def _to_entity(row: DocumentRow) -> Document:
    title = _required(row.title, "title")
    file_path = _required(row.file_path, "file_path")
    content_type = _required(row.content_type, "content_type")
    status = _document_status(_required(row.status, "status"))
    partial_extraction = _required(row.partial_extraction, "partial_extraction")
    created_at = _required(row.created_at, "created_at")
    contractor_entity_id = (
        ContractorEntityId(row.contractor_entity_id)
        if row.contractor_entity_id is not None
        else None
    )
    return Document(
        id=DocumentId(row.id),
        contractor_entity_id=contractor_entity_id,
        title=title,
        file_path=file_path,
        content_type=content_type,
        document_kind=row.document_kind,
        doc_type=row.doc_type,
        status=status,
        error_message=row.error_message,
        partial_extraction=partial_extraction,
        created_at=created_at,
    )


def _required[RequiredValue](
    value: RequiredValue | None,
    field_name: str,
) -> RequiredValue:
    if value is None:
        raise ValueError(f"Document row is missing {field_name}")
    return value


def _document_status(value: str) -> DocumentStatus:
    try:
        return DocumentStatus(value)
    except ValueError as exc:
        raise ValueError(f"Document row has invalid status: {value}") from exc


__all__ = ["SqlAlchemyDocumentRepository"]
