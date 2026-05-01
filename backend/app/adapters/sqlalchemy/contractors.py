from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import (
    Contractor as ContractorRow,
)
from app.adapters.sqlalchemy.models import (
    ContractorRawMapping as ContractorRawMappingRow,
)
from app.adapters.sqlalchemy.models import (
    Document as DocumentRow,
)
from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.entities.resolution import RawContractorMapping
from app.features.contractors.ports import ContractorNotFound
from app.features.ingest.entities.document import Document, DocumentStatus


class SqlAlchemyContractorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, contractor: Contractor) -> None:
        stmt = insert(ContractorRow).values(
            id=contractor.id,
            display_name=contractor.display_name,
            normalized_key=contractor.normalized_key,
            inn=contractor.inn,
            kpp=contractor.kpp,
        )
        await self._session.execute(stmt)

    async def get(self, id: ContractorEntityId) -> Contractor:
        stmt = select(ContractorRow).where(ContractorRow.id == id)
        row = await self._session.scalar(stmt)
        if row is None:
            raise ContractorNotFound(id)
        return _contractor_to_entity(row)

    async def get_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, Contractor]:
        if not ids:
            return {}

        stmt = select(ContractorRow).where(ContractorRow.id.in_(ids))
        rows = await self._session.scalars(stmt)
        contractors = [_contractor_to_entity(row) for row in rows]
        return {contractor.id: contractor for contractor in contractors}

    async def find_by_inn(self, inn: str) -> Contractor | None:
        stmt = select(ContractorRow).where(ContractorRow.inn == inn)
        row = await self._session.scalar(stmt)
        return _contractor_to_entity(row) if row is not None else None

    async def find_by_normalized_key(self, key: str) -> Contractor | None:
        stmt = select(ContractorRow).where(ContractorRow.normalized_key == key)
        row = await self._session.scalar(stmt)
        return _contractor_to_entity(row) if row is not None else None

    async def find_all_for_fuzzy(self) -> list[Contractor]:
        stmt = select(ContractorRow)
        rows = await self._session.scalars(stmt)
        return [_contractor_to_entity(r) for r in rows]

    async def count_documents_for(self, id: ContractorEntityId) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentRow)
            .where(DocumentRow.contractor_entity_id == id)
        )
        return await self._session.scalar(stmt) or 0

    async def list_for_contractor(
        self,
        id: ContractorEntityId,
        *,
        limit: int,
        offset: int,
    ) -> list[Document]:
        stmt = (
            select(DocumentRow)
            .where(DocumentRow.contractor_entity_id == id)
            .order_by(DocumentRow.created_at.desc(), DocumentRow.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.scalars(stmt)
        return [_document_to_entity(r) for r in rows]


class SqlAlchemyRawContractorMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, mapping: RawContractorMapping) -> None:
        stmt = insert(ContractorRawMappingRow).values(
            id=mapping.id,
            raw_name=mapping.raw_name,
            inn=mapping.inn,
            contractor_entity_id=mapping.contractor_entity_id,
            confidence=mapping.confidence,
        )
        await self._session.execute(stmt)

    async def count_for(self, contractor_id: ContractorEntityId) -> int:
        stmt = (
            select(func.count())
            .select_from(ContractorRawMappingRow)
            .where(ContractorRawMappingRow.contractor_entity_id == contractor_id)
        )
        return await self._session.scalar(stmt) or 0


def _contractor_to_entity(row: ContractorRow) -> Contractor:
    return Contractor(
        id=ContractorEntityId(row.id),
        display_name=_required(row.display_name, "contractors.display_name"),
        normalized_key=_required(row.normalized_key, "contractors.normalized_key"),
        inn=row.inn,
        kpp=row.kpp,
        created_at=_required(row.created_at, "contractors.created_at"),
    )


def _document_to_entity(row: DocumentRow) -> Document:
    contractor_entity_id = (
        ContractorEntityId(row.contractor_entity_id)
        if row.contractor_entity_id is not None
        else None
    )
    return Document(
        id=DocumentId(row.id),
        contractor_entity_id=contractor_entity_id,
        title=_required(row.title, "documents.title"),
        file_path=_required(row.file_path, "documents.file_path"),
        content_type=_required(row.content_type, "documents.content_type"),
        document_kind=row.document_kind,
        doc_type=row.doc_type,
        status=DocumentStatus(_required(row.status, "documents.status")),
        error_message=row.error_message,
        partial_extraction=_required(
            row.partial_extraction,
            "documents.partial_extraction",
        ),
        created_at=_required(row.created_at, "documents.created_at"),
    )


def _required[T](value: T | None, field_name: str) -> T:
    if value is None:
        raise ValueError(f"Expected non-null value for {field_name}")
    return value


__all__ = [
    "SqlAlchemyContractorRepository",
    "SqlAlchemyRawContractorMappingRepository",
]
