# Document Ingestion To Catalog Plan

## Goal

Keep PDF upload and the existing document intelligence flow available, but move document-to-catalog extraction out of the MVP critical path. CSV import, catalog embeddings, `search_items` and unified chat must work before PDF extraction starts producing `price_items`.

## MVP Rule

Do not change the existing document lifecycle during the catalog MVP:

```text
QUEUED -> PROCESSING -> RESOLVING -> INDEXING -> INDEXED
```

Rules:

- Do not add new document statuses for catalog work.
- Do not change the Celery task chain for the MVP catalog implementation.
- Do not require PDF extraction to populate `price_items`.
- Do not make document chunks or summaries the primary search result for the assistant.
- Do not use document chunks as the main evidence for catalog search while CSV-derived `price_items` are the MVP source of truth.
- Keep document search and summary as additional features to continue improving after MVP.

## What Remains Available In MVP

The existing PDF/document features remain available as-is:

```text
PDF upload
  -> existing SAGE processing
  -> existing chunks, extracted contract fields and summary
  -> existing contractor resolution
  -> existing document chunk indexing
  -> existing document drill-down search and summary surfaces
```

The catalog MVP can link to these features later, but it must not depend on them.

## Document RAG Boundary

Document search, drill-down and summaries remain valuable side features, but they are not the product basis for catalog search.

Rules:

- Document summary/RAG can answer questions about uploaded PDFs in the document workflow.
- Catalog search must return `price_items` cards/table from Postgres as its primary evidence.
- Assistant prose may mention document context only when the UI can show the document source separately.
- A document chunk or summary must not replace a catalog row when the user asks for price, supplier, unit, city or source.
- If PDF extraction later finds a service/product/cost line, it must be normalized into `price_items`, indexed into `price_items_search_v1` and shown as a catalog card with document provenance.

## Post-MVP Adaptation Strategy

After the CSV/search/chat baseline is stable, add a document extraction path that emits catalog-compatible rows.

```text
PDF upload
  -> existing document pipeline
  -> SAGE extracts PriceItemExtraction[]
  -> normalize with the same catalog normalization functions as CSV
  -> build embedding_text with prices_v1
  -> upsert into price_items
  -> index through the same IndexPriceItemsUseCase into price_items_search_v1
  -> keep document_id/page/chunk/source_text as evidence
```

The extracted rows must use the same catalog contract as CSV rows. The only difference is provenance.

For the assistant/UI, document-derived rows should behave like CSV-derived catalog rows:

- hydrate full card fields from Postgres;
- show `source_text_snippet` in search results and full `source_text` with document/page/chunk provenance in detail;
- keep the live assistant explanation separate from the row evidence;
- never require the user to trust a prose summary without an inspectable item card.

## Future SAGE Output Contract

Add only in the post-MVP document extraction phase:

```python
class PriceItemExtraction(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    unit_price: str | None = None
    source_text: str | None = None
    section: str | None = None
    supplier: str | None = None
    has_vat: str | None = None
    supplier_inn: str | None = None
    supplier_city: str | None = None
    supplier_phone: str | None = None
    supplier_email: str | None = None
    supplier_status: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    chunk_index: int | None = None
    confidence: float | None = None
```

Extend `ProcessingResult` only after the catalog MVP is working:

```python
class ProcessingResult(BaseModel):
    chunks: list[Chunk]
    fields: ContractFields
    price_items: list[PriceItemExtraction] = Field(default_factory=list)
    summary: str
    pages: list[Page]
    document_kind: Literal["text", "scan"]
    partial: bool
    failed_chunk_indices: list[int] = Field(default_factory=list)
    preview_pdf_path: str | None = None
```

`ContractFields` remains for current contractor/document workflows. `PriceItemExtraction[]` is an additive catalog source.

## Future Extraction Prompt Requirements

When the post-MVP phase starts, update `packages/sage/sage/llm/prompts.py` to return:

```json
{
  "contract_fields": {},
  "price_items": []
}
```

Rules:

- Do not invent catalog fields.
- Return `null` for unknown values.
- Extract one item per concrete service, product, rental, catering, accommodation or event cost line.
- Preserve Russian wording for names, categories, units and VAT.
- Use exact source fragments in `source_text` when available.
- Keep page/chunk provenance when the caller can supply it.
- Let backend catalog normalization reject or warn on invalid rows.

## Future Backend Storage Flow

### Create

- `backend/app/features/catalog/use_cases/upsert_document_price_items.py` - normalizes `PriceItemExtraction[]` and writes document-derived `price_items`.
- `backend/app/features/catalog/use_cases/link_document_price_items.py` - links unresolved document-derived rows after contractor resolution if needed.

### Modify

- `packages/sage/sage/models.py` - add `PriceItemExtraction` and `ProcessingResult.price_items`.
- `packages/sage/sage/llm/prompts.py` - request catalog-compatible extraction.
- `packages/sage/sage/llm/extract.py` - parse the new response shape.
- `packages/sage/sage/process.py` - return extracted price items without side effects.
- `backend/app/features/ingest/use_cases/process_document.py` - store extracted candidates after existing document fields/summaries are stored.
- `backend/app/features/contractors/use_cases/resolve_contractor.py` - link document-derived rows after contractor resolution.
- `backend/app/features/ingest/use_cases/index_document.py` - index related catalog rows after existing document chunk indexing remains consistent.
- `backend/app/entrypoints/celery/composition.py` - wire new catalog use cases without changing task names.
- `backend/app/entrypoints/celery/tasks/ingest.py` - keep orchestration thin and preserve statuses.

## Future Provenance Rules

Document-derived catalog rows should add provenance fields or source records:

```text
source_kind = document_extraction
source_document_id = documents.id
source_page_start = extracted.page_start
source_page_end = extracted.page_end
source_chunk_index = extracted.chunk_index
source_text = extracted.source_text
```

If contractor resolution has not completed:

```text
contractor_entity_id = null
```

After `resolve_contractor`, update document-derived rows for that document.

## Failure Behavior For Post-MVP

- If SAGE extracts no price items, the document can still become `INDEXED`.
- If one extracted item is invalid, store row-level error/provenance and continue with other items.
- If catalog indexing fails after document indexing, fail only the stage that cannot complete consistently and preserve a useful error message.
- Do not put row-level catalog extraction errors into `documents.error_message` unless the whole document stage fails.

## Testing Plan For Post-MVP

- [ ] Add `packages/sage/tests/test_models.py` coverage for `PriceItemExtraction` defaults and `ProcessingResult.price_items`.
- [ ] Add `packages/sage/tests/test_llm.py` coverage for parsing `{contract_fields, price_items}`.
- [ ] Add `backend/tests/features/ingest/use_cases/test_process_document.py` case where document processing stores extracted catalog candidates.
- [ ] Add `backend/tests/features/contractors/use_cases/test_resolve_contractor.py` case where resolving a contractor links document-derived rows.
- [ ] Add `backend/tests/features/ingest/use_cases/test_index_document.py` case where document indexing also indexes related catalog rows.
- [ ] Add regression coverage that existing PDF upload/status/document drill-down search still works without extracted price items.

Focused checks:

```bash
uv run --project packages/sage pytest packages/sage/tests/test_models.py packages/sage/tests/test_llm.py -v
uv run --project backend pytest backend/tests/features/ingest/use_cases/test_process_document.py -v
uv run --project backend pytest backend/tests/features/contractors/use_cases/test_resolve_contractor.py -v
uv run --project backend pytest backend/tests/features/ingest/use_cases/test_index_document.py -v
```
