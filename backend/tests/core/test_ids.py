from uuid import UUID, uuid4

from app.core.domain import (
    ChunkId,
    ContractorEntityId,
    DocumentId,
    new_chunk_id,
    new_contractor_entity_id,
    new_document_id,
)


def test_id_factories_return_uuid_values() -> None:
    assert isinstance(new_document_id(), UUID)
    assert isinstance(new_contractor_entity_id(), UUID)
    assert isinstance(new_chunk_id(), UUID)


def test_document_id_round_trips_through_string_uuid() -> None:
    value = uuid4()

    assert UUID(str(DocumentId(value))) == value


def test_id_newtypes_are_distinct_static_type_markers() -> None:
    assert DocumentId is not ContractorEntityId
    assert DocumentId.__name__ == "DocumentId"
    assert ContractorEntityId.__name__ == "ContractorEntityId"
    assert ChunkId.__name__ == "ChunkId"

    # Static type checkers reject this mismatch:
    # accepts_document_id(new_contractor_entity_id())  # type: ignore[arg-type]
