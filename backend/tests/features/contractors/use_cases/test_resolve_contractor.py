from collections.abc import MutableSequence
from datetime import UTC, datetime
from types import TracebackType
from uuid import uuid4

from app.core.domain.ids import ContractorEntityId, DocumentId, new_contractor_entity_id
from app.features.contractors.entities.contractor import Contractor
from app.features.contractors.entities.resolution import RawContractorMapping
from app.features.contractors.use_cases.resolve_contractor import (
    FUZZY_MATCH_THRESHOLD,
    InvalidDocumentStatusForResolution,
    ResolveContractorUseCase,
)
from app.features.ingest.entities.document import Document, DocumentStatus
from sage import ContractFields

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeContractorRepository:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.by_inn: dict[str, Contractor] = {}
        self.by_key: dict[str, Contractor] = {}
        self.fuzzy_pool: list[Contractor] = []
        self.added: list[Contractor] = []

    async def find_by_inn(self, inn: str) -> Contractor | None:
        self.calls.append("contractors.find_by_inn")
        return self.by_inn.get(inn)

    async def find_by_normalized_key(self, key: str) -> Contractor | None:
        self.calls.append("contractors.find_by_normalized_key")
        return self.by_key.get(key)

    async def find_all_for_fuzzy(self) -> list[Contractor]:
        self.calls.append("contractors.find_all_for_fuzzy")
        return list(self.fuzzy_pool)

    async def add(self, contractor: Contractor) -> None:
        self.calls.append("contractors.add")
        self.added.append(contractor)

    async def get(self, id: ContractorEntityId) -> Contractor:  # pragma: no cover
        raise NotImplementedError

    async def get_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, Contractor]:  # pragma: no cover
        raise NotImplementedError

    async def count_documents_for(
        self,
        id: ContractorEntityId,
    ) -> int:  # pragma: no cover
        raise NotImplementedError

    async def count_documents_for_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, int]:  # pragma: no cover
        raise NotImplementedError

    async def list_for_contractor(
        self,
        id: ContractorEntityId,
        *,
        limit: int,
        offset: int,
    ) -> list[Document]:  # pragma: no cover
        raise NotImplementedError

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        q: str | None = None,
    ) -> list[Contractor]:  # pragma: no cover
        raise NotImplementedError


class FakeRawContractorMappingRepository:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.added: list[RawContractorMapping] = []

    async def add(self, mapping: RawContractorMapping) -> None:
        self.calls.append("mappings.add")
        self.added.append(mapping)

    async def count_for(
        self,
        contractor_id: ContractorEntityId,
    ) -> int:  # pragma: no cover
        raise NotImplementedError


class FakeDocumentRepository:
    def __init__(self, calls: MutableSequence[str], document: Document) -> None:
        self.calls = calls
        self._document = document
        self.contractor_id_updates: list[
            tuple[DocumentId, ContractorEntityId | None]
        ] = []

    async def get(self, document_id: DocumentId) -> Document:
        self.calls.append("documents.get")
        return self._document

    async def get_many(self, ids: list[DocumentId]) -> dict[DocumentId, Document]:
        raise NotImplementedError

    async def add(self, document: Document) -> None:  # pragma: no cover
        raise NotImplementedError

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        status: DocumentStatus | None = None,
        contractor_entity_id: ContractorEntityId | None = None,
    ) -> list[Document]:  # pragma: no cover
        raise NotImplementedError

    async def update_status(
        self,
        document_id: DocumentId,
        status: DocumentStatus,
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def update_processing_result(
        self,
        document_id: DocumentId,
        *,
        document_kind: str,
        partial_extraction: bool,
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def set_error(
        self,
        document_id: DocumentId,
        message: str,
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def set_preview_file_path(
        self,
        document_id: DocumentId,
        preview_file_path: str | None,
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def set_contractor_entity_id(
        self,
        document_id: DocumentId,
        contractor_entity_id: ContractorEntityId | None,
    ) -> None:
        self.calls.append("documents.set_contractor_entity_id")
        self.contractor_id_updates.append((document_id, contractor_entity_id))


class FakeFieldsRepository:
    def __init__(
        self,
        calls: MutableSequence[str],
        fields: ContractFields | None,
    ) -> None:
        self.calls = calls
        self._fields = fields

    async def get(self, document_id: DocumentId) -> ContractFields | None:
        self.calls.append("fields.get")
        return self._fields

    async def upsert(
        self,
        document_id: DocumentId,
        fields: ContractFields,
    ) -> None:  # pragma: no cover
        raise NotImplementedError


class FakeUnitOfWork:
    def __init__(self, calls: MutableSequence[str]) -> None:
        self.calls = calls
        self.commits = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        self.calls.append("uow.enter")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.calls.append("uow.exit")

    async def commit(self) -> None:
        self.commits += 1
        self.calls.append(f"uow.commit:{self.commits}")

    async def rollback(self) -> None:
        self.calls.append("uow.rollback")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _document(
    document_id: DocumentId,
    *,
    status: DocumentStatus = DocumentStatus.RESOLVING,
) -> Document:
    return Document(
        id=document_id,
        contractor_entity_id=None,
        title="contract.pdf",
        file_path="/fake/uploads/contract.pdf",
        content_type="application/pdf",
        document_kind=None,
        doc_type=None,
        status=status,
        error_message=None,
        partial_extraction=False,
        created_at=datetime.now(UTC),
    )


def _contractor(*, normalized_key: str, inn: str | None = None) -> Contractor:
    return Contractor(
        id=new_contractor_entity_id(),
        display_name="Existing Contractor",
        normalized_key=normalized_key,
        inn=inn,
        kpp=None,
        created_at=datetime.now(UTC),
    )


def _use_case(
    *,
    calls: MutableSequence[str],
    contractors: FakeContractorRepository,
    mappings: FakeRawContractorMappingRepository,
    documents: FakeDocumentRepository,
    fields: FakeFieldsRepository,
    uow: FakeUnitOfWork,
) -> ResolveContractorUseCase:
    return ResolveContractorUseCase(
        contractors=contractors,
        mappings=mappings,
        documents=documents,
        fields=fields,
        uow=uow,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_inn_exact_match() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    existing = _contractor(normalized_key="вектор", inn="7701234567")
    contractors = FakeContractorRepository(calls)
    contractors.by_inn["7701234567"] = existing
    mappings = FakeRawContractorMappingRepository(calls)
    documents = FakeDocumentRepository(calls, _document(document_id))
    fields = FakeFieldsRepository(
        calls,
        ContractFields(supplier_name="ООО Вектор", supplier_inn="7701234567"),
    )
    uow = FakeUnitOfWork(calls)

    result = await _use_case(
        calls=calls,
        contractors=contractors,
        mappings=mappings,
        documents=documents,
        fields=fields,
        uow=uow,
    ).execute(document_id)

    assert result == existing.id
    assert len(mappings.added) == 1
    assert mappings.added[0].contractor_entity_id == existing.id
    assert mappings.added[0].confidence == 1.0
    assert mappings.added[0].inn == "7701234567"
    assert documents.contractor_id_updates == [(document_id, existing.id)]
    assert uow.commits == 1
    assert "contractors.find_by_inn" in calls
    assert "contractors.find_by_normalized_key" not in calls
    assert "contractors.add" not in calls


async def test_normalized_key_match_no_inn() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    existing = _contractor(normalized_key="вектор")
    contractors = FakeContractorRepository(calls)
    contractors.by_key["вектор"] = existing
    mappings = FakeRawContractorMappingRepository(calls)
    documents = FakeDocumentRepository(calls, _document(document_id))
    fields = FakeFieldsRepository(calls, ContractFields(supplier_name="ООО Вектор"))
    uow = FakeUnitOfWork(calls)

    result = await _use_case(
        calls=calls,
        contractors=contractors,
        mappings=mappings,
        documents=documents,
        fields=fields,
        uow=uow,
    ).execute(document_id)

    assert result == existing.id
    assert mappings.added[0].confidence == 1.0
    assert documents.contractor_id_updates == [(document_id, existing.id)]
    assert "contractors.find_by_inn" not in calls
    assert "contractors.find_by_normalized_key" in calls
    assert "contractors.add" not in calls


async def test_fuzzy_match_above_threshold() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    existing = _contractor(normalized_key="вектор")
    contractors = FakeContractorRepository(calls)
    contractors.fuzzy_pool = [existing]
    mappings = FakeRawContractorMappingRepository(calls)
    documents = FakeDocumentRepository(calls, _document(document_id))
    fields = FakeFieldsRepository(calls, ContractFields(supplier_name="ООО Вектор"))
    uow = FakeUnitOfWork(calls)

    result = await _use_case(
        calls=calls,
        contractors=contractors,
        mappings=mappings,
        documents=documents,
        fields=fields,
        uow=uow,
    ).execute(document_id)

    assert result == existing.id
    assert mappings.added[0].confidence == 1.0
    assert "contractors.find_all_for_fuzzy" in calls
    assert "contractors.add" not in calls


async def test_fuzzy_match_below_threshold_creates_new() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    unrelated = _contractor(normalized_key="абсолютно другое имя предприятия")
    contractors = FakeContractorRepository(calls)
    contractors.fuzzy_pool = [unrelated]
    mappings = FakeRawContractorMappingRepository(calls)
    documents = FakeDocumentRepository(calls, _document(document_id))
    fields = FakeFieldsRepository(
        calls,
        ContractFields(supplier_name="Вектор", supplier_kpp="770101001"),
    )
    uow = FakeUnitOfWork(calls)

    result = await _use_case(
        calls=calls,
        contractors=contractors,
        mappings=mappings,
        documents=documents,
        fields=fields,
        uow=uow,
    ).execute(document_id)

    assert result is not None
    assert result != unrelated.id
    assert len(contractors.added) == 1
    new_contractor = contractors.added[0]
    assert new_contractor.id == result
    assert new_contractor.normalized_key == "вектор"
    assert new_contractor.kpp == "770101001"
    assert mappings.added[0].confidence == 1.0
    assert documents.contractor_id_updates == [(document_id, result)]


async def test_empty_fuzzy_pool_creates_new() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    contractors = FakeContractorRepository(calls)
    contractors.fuzzy_pool = []
    mappings = FakeRawContractorMappingRepository(calls)
    documents = FakeDocumentRepository(calls, _document(document_id))
    fields = FakeFieldsRepository(calls, ContractFields(supplier_name="Вектор"))
    uow = FakeUnitOfWork(calls)

    result = await _use_case(
        calls=calls,
        contractors=contractors,
        mappings=mappings,
        documents=documents,
        fields=fields,
        uow=uow,
    ).execute(document_id)

    assert result is not None
    assert len(contractors.added) == 1
    assert contractors.added[0].id == result
    assert uow.commits == 1


async def test_empty_raw_name_returns_none() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    contractors = FakeContractorRepository(calls)
    mappings = FakeRawContractorMappingRepository(calls)
    documents = FakeDocumentRepository(calls, _document(document_id))
    fields = FakeFieldsRepository(calls, ContractFields(supplier_name=""))
    uow = FakeUnitOfWork(calls)

    result = await _use_case(
        calls=calls,
        contractors=contractors,
        mappings=mappings,
        documents=documents,
        fields=fields,
        uow=uow,
    ).execute(document_id)

    assert result is None
    assert documents.contractor_id_updates == [(document_id, None)]
    assert uow.commits == 1
    assert len(mappings.added) == 0
    assert "contractors.find_by_inn" not in calls
    assert "contractors.find_by_normalized_key" not in calls
    assert "contractors.find_all_for_fuzzy" not in calls
    assert "contractors.add" not in calls


async def test_invalid_document_status_raises() -> None:
    calls: list[str] = []
    document_id = DocumentId(uuid4())
    contractors = FakeContractorRepository(calls)
    mappings = FakeRawContractorMappingRepository(calls)
    documents = FakeDocumentRepository(
        calls,
        _document(document_id, status=DocumentStatus.PROCESSING),
    )
    fields = FakeFieldsRepository(calls, ContractFields(supplier_name="ООО Вектор"))
    uow = FakeUnitOfWork(calls)

    try:
        await _use_case(
            calls=calls,
            contractors=contractors,
            mappings=mappings,
            documents=documents,
            fields=fields,
            uow=uow,
        ).execute(document_id)
        raise AssertionError("InvalidDocumentStatusForResolution was not raised")
    except InvalidDocumentStatusForResolution as exc:
        assert exc.document_id == document_id
        assert exc.status is DocumentStatus.PROCESSING

    assert "fields.get" not in calls
    assert "documents.set_contractor_entity_id" not in calls
    assert uow.commits == 0


def test_fuzzy_threshold_is_named_constant() -> None:
    assert FUZZY_MATCH_THRESHOLD == 90
