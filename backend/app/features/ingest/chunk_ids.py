from uuid import NAMESPACE_OID, UUID, uuid5

from app.core.domain.ids import DocumentId


def stable_chunk_id(document_id: DocumentId, chunk_index: int) -> UUID:
    return uuid5(NAMESPACE_OID, f"{document_id}:{chunk_index}")


def stable_summary_id(document_id: DocumentId) -> UUID:
    return uuid5(NAMESPACE_OID, f"{document_id}:summary")


__all__ = ["stable_chunk_id", "stable_summary_id"]
