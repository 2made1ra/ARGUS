from typing import Any

from app.core.domain.ids import DocumentId
from app.core.ports.unit_of_work import UnitOfWork
from app.features.contractors.ports import ContractorRepository
from app.features.ingest.chunk_ids import stable_chunk_id, stable_summary_id
from app.features.ingest.entities.document import DocumentStatus
from app.features.ingest.ports import (
    ChunkRepository,
    DocumentRepository,
    EmbeddingService,
    FieldsRepository,
    SummaryRepository,
    VectorIndex,
    VectorPoint,
)

_MAX_PAYLOAD_TEXT_LENGTH = 8000


class IndexDocumentUseCase:
    def __init__(
        self,
        *,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        fields: FieldsRepository,
        summaries: SummaryRepository,
        contractors: ContractorRepository,
        embeddings: EmbeddingService,
        index: VectorIndex,
        uow: UnitOfWork,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._fields = fields
        self._summaries = summaries
        self._contractors = contractors
        self._embeddings = embeddings
        self._index = index
        self._uow = uow

    async def execute(self, document_id: DocumentId) -> None:
        async with self._uow:
            document = await self._documents.get(document_id)
            document.mark_indexing()
            await self._documents.update_status(document_id, DocumentStatus.INDEXING)
            await self._uow.commit()

        try:
            async with self._uow:
                document = await self._documents.get(document_id)
                chunks = await self._chunks.list_for(document_id)
                fields = await self._fields.get(document_id)
                summary = await self._summaries.get(document_id)
                if document.contractor_entity_id is not None:
                    await self._contractors.get(document.contractor_entity_id)

            document_date = fields.document_date if fields is not None else None
            points = [
                VectorPoint(
                    id=stable_chunk_id(document_id, chunk.chunk_index),
                    vector=[],
                    payload={
                        "document_id": str(document_id),
                        "contractor_entity_id": _optional_uuid(
                            document.contractor_entity_id,
                        ),
                        "doc_type": document.doc_type,
                        "document_kind": document.document_kind,
                        "date": document_date,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "section_type": chunk.section_type,
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text[:_MAX_PAYLOAD_TEXT_LENGTH],
                        "is_summary": False,
                    },
                )
                for chunk in chunks
            ]

            if summary is not None:
                summary_text, _key_points = summary
                points.append(
                    VectorPoint(
                        id=stable_summary_id(document_id),
                        vector=[],
                        payload={
                            "document_id": str(document_id),
                            "contractor_entity_id": _optional_uuid(
                                document.contractor_entity_id,
                            ),
                            "doc_type": document.doc_type,
                            "document_kind": document.document_kind,
                            "date": document_date,
                            "page_start": None,
                            "page_end": None,
                            "section_type": None,
                            "chunk_index": -1,
                            "text": summary_text[:_MAX_PAYLOAD_TEXT_LENGTH],
                            "is_summary": True,
                        },
                    ),
                )

            texts = [str(point.payload["text"]) for point in points]
            vectors = await self._embeddings.embed(texts)
            for point, vector in zip(points, vectors, strict=True):
                point.vector = vector

            await self._index.upsert_chunks(points)

            async with self._uow:
                document = await self._documents.get(document_id)
                document.mark_indexed()
                await self._documents.update_status(document_id, DocumentStatus.INDEXED)
                await self._uow.commit()
        except Exception as exc:
            async with self._uow:
                document = await self._documents.get(document_id)
                document.mark_failed(str(exc))
                await self._documents.set_error(document_id, str(exc))
                await self._uow.commit()
            raise


def _optional_uuid(value: Any | None) -> str | None:
    return str(value) if value is not None else None


__all__ = ["IndexDocumentUseCase"]
