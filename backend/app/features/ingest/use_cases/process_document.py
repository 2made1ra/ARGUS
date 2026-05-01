from pathlib import Path

from app.core.domain.ids import DocumentId
from app.core.ports.unit_of_work import UnitOfWork
from app.features.ingest.entities.document import DocumentStatus
from app.features.ingest.ports import (
    ChunkRepository,
    DocumentRepository,
    FieldsRepository,
    SageProcessor,
    SummaryRepository,
)


class ProcessDocumentUseCase:
    def __init__(
        self,
        *,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        fields: FieldsRepository,
        summaries: SummaryRepository,
        sage: SageProcessor,
        uow: UnitOfWork,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._fields = fields
        self._summaries = summaries
        self._sage = sage
        self._uow = uow

    async def execute(self, document_id: DocumentId) -> None:
        async with self._uow:
            document = await self._documents.get(document_id)
            document.mark_processing()
            await self._documents.update_status(document_id, DocumentStatus.PROCESSING)
            await self._uow.commit()

        try:
            result = await self._sage.process(Path(document.file_path))

            async with self._uow:
                await self._chunks.add_many(document_id, result.chunks)
                await self._fields.upsert(document_id, result.fields)
                await self._summaries.upsert(document_id, result.summary, [])
                await self._documents.update_processing_result(
                    document_id,
                    document_kind=result.document_kind,
                    partial_extraction=result.partial,
                )
                await self._uow.commit()
        except Exception as exc:
            async with self._uow:
                await self._documents.set_error(document_id, str(exc))
                await self._uow.commit()
            raise


__all__ = ["ProcessDocumentUseCase"]
