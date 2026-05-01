import uuid
from typing import NewType
from uuid import UUID

DocumentId = NewType("DocumentId", UUID)
ContractorEntityId = NewType("ContractorEntityId", UUID)
ChunkId = NewType("ChunkId", UUID)


def new_document_id() -> DocumentId:
    return DocumentId(uuid.uuid4())


def new_contractor_entity_id() -> ContractorEntityId:
    return ContractorEntityId(uuid.uuid4())


def new_chunk_id() -> ChunkId:
    return ChunkId(uuid.uuid4())


__all__ = [
    "ChunkId",
    "ContractorEntityId",
    "DocumentId",
    "new_chunk_id",
    "new_contractor_entity_id",
    "new_document_id",
]
