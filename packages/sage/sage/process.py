import os
from pathlib import Path

from sage.chunker import chunk_pages
from sage.conversion import ensure_pdf
from sage.llm import LMStudioClient, extract_one, merge_fields, summarize
from sage.models import ContractFields, ProcessingResult
from sage.normalizer import normalize_pages
from sage.pdf import detect_kind, extract_text_pages, ocr_pages


async def process_document(
    src: Path,
    work_dir: Path,
    *,
    llm_client: LMStudioClient | None = None,
) -> ProcessingResult:
    _owns_client = llm_client is None
    client = llm_client or LMStudioClient(
        base_url=os.environ["LM_STUDIO_URL"],
        model=os.environ["LM_STUDIO_LLM_MODEL"],
    )
    if _owns_client:
        async with client:
            return await _run_pipeline(client, src, work_dir)
    return await _run_pipeline(client, src, work_dir)


async def _run_pipeline(
    client: LMStudioClient,
    src: Path,
    work_dir: Path,
) -> ProcessingResult:
    pdf_path = await ensure_pdf(src, work_dir)
    kind = detect_kind(pdf_path)
    pages = extract_text_pages(pdf_path) if kind == "text" else ocr_pages(pdf_path)
    pages = normalize_pages(pages)
    chunks = chunk_pages(pages)

    fields = ContractFields()
    partial = False
    for chunk in chunks:
        chunk_fields = await extract_one(client, chunk)
        partial = partial or _all_fields_none(chunk_fields)
        fields = merge_fields(fields, chunk_fields)

    summary = await summarize(client, pages)

    return ProcessingResult(
        chunks=chunks,
        fields=fields,
        summary=summary,
        pages=pages,
        document_kind=kind,
        partial=partial,
    )


def _all_fields_none(fields: ContractFields) -> bool:
    return all(value is None for value in fields.model_dump().values())
