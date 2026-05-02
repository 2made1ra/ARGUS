import os
from pathlib import Path

from sage.chunker import chunk_pages
from sage.conversion import ensure_pdf
from sage.llm import (
    LMStudioClient,
    extract_one,
    merge_fields,
    summarize,
    summarize_chunk,
)
from sage.llm.client import ChatClient
from sage.models import ContractFields, ProcessingResult
from sage.normalizer import normalize_pages
from sage.pdf import DetectorConfig, detect_kind, extract_text_pages, ocr_pages


async def process_document(
    src: Path,
    work_dir: Path,
    *,
    llm_client: ChatClient | None = None,
    detector_config: DetectorConfig | None = None,
) -> ProcessingResult:
    if llm_client is None:
        client = LMStudioClient(
            base_url=os.environ["LM_STUDIO_URL"],
            model=os.environ["LM_STUDIO_LLM_MODEL"],
        )
        async with client:
            return await _run_pipeline(client, src, work_dir, detector_config)

    return await _run_pipeline(llm_client, src, work_dir, detector_config)


async def _run_pipeline(
    client: ChatClient,
    src: Path,
    work_dir: Path,
    detector_config: DetectorConfig | None,
) -> ProcessingResult:
    pdf_path = await ensure_pdf(src, work_dir)
    kind = (
        detect_kind(pdf_path, detector_config)
        if detector_config is not None
        else detect_kind(pdf_path)
    )
    pages = extract_text_pages(pdf_path) if kind == "text" else ocr_pages(pdf_path)
    pages = normalize_pages(pages)
    chunks = chunk_pages(pages)

    fields = ContractFields()
    partial = False
    failed_chunk_indices: list[int] = []
    for chunk in chunks:
        chunk_fields = await extract_one(client, chunk)
        if _all_fields_none(chunk_fields):
            partial = True
            failed_chunk_indices.append(chunk.chunk_index)
        chunk.chunk_summary = await summarize_chunk(client, chunk)
        fields = merge_fields(fields, chunk_fields)

    summary = await summarize(client, pages)

    return ProcessingResult(
        chunks=chunks,
        fields=fields,
        summary=summary,
        pages=pages,
        document_kind=kind,
        partial=partial,
        failed_chunk_indices=failed_chunk_indices,
        preview_pdf_path=str(pdf_path),
    )


def _all_fields_none(fields: ContractFields) -> bool:
    return all(value is None for value in fields.model_dump().values())
