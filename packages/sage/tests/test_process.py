from pathlib import Path
from typing import Any

import pytest
from sage.models import Chunk, ContractFields, Page, ProcessingResult
from sage.process import process_document


class StubClient:
    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError


def make_chunk(index: int) -> Chunk:
    return Chunk(
        text=f"chunk {index}",
        page_start=index + 1,
        page_end=index + 1,
        section_type=None,
        chunk_index=index,
        chunk_summary=None,
    )


async def test_process_document_orchestrates_text_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    src = tmp_path / "source.docx"
    pdf_path = tmp_path / "source.pdf"
    client = StubClient()
    raw_pages = [Page(index=1, text=" raw text ", kind="text")]
    normalized_pages = [Page(index=1, text="raw text", kind="text")]
    chunks = [make_chunk(0), make_chunk(1)]
    first_fields = ContractFields(document_number="42")
    second_fields = ContractFields()
    merged_once = ContractFields(document_number="42")
    merged_twice = ContractFields(document_number="42")

    async def fake_ensure_pdf(received_src: Path, received_work_dir: Path) -> Path:
        assert received_src == src
        assert received_work_dir == tmp_path
        calls.append("ensure_pdf")
        return pdf_path

    def fake_detect_kind(received_pdf_path: Path) -> str:
        assert received_pdf_path == pdf_path
        calls.append("detect_kind")
        return "text"

    def fake_extract_text_pages(received_pdf_path: Path) -> list[Page]:
        assert received_pdf_path == pdf_path
        calls.append("extract_text_pages")
        return raw_pages

    def fake_ocr_pages(received_pdf_path: Path) -> list[Page]:
        pytest.fail(
            f"ocr_pages should not be called for text PDFs: {received_pdf_path}"
        )

    def fake_normalize_pages(received_pages: list[Page]) -> list[Page]:
        assert received_pages == raw_pages
        calls.append("normalize_pages")
        return normalized_pages

    def fake_chunk_pages(received_pages: list[Page]) -> list[Chunk]:
        assert received_pages == normalized_pages
        calls.append("chunk_pages")
        return chunks

    async def fake_extract_one(
        received_client: StubClient, chunk: Chunk
    ) -> ContractFields:
        assert received_client is client
        calls.append(f"extract_one:{chunk.chunk_index}")
        return first_fields if chunk.chunk_index == 0 else second_fields

    async def fake_summarize_chunk(received_client: StubClient, chunk: Chunk) -> str:
        assert received_client is client
        calls.append(f"summarize_chunk:{chunk.chunk_index}")
        return f"summary {chunk.chunk_index}"

    def fake_merge_fields(
        left: ContractFields,
        right: ContractFields,
    ) -> ContractFields:
        calls.append(f"merge_fields:{right.document_number or 'none'}")
        if right == first_fields:
            assert left == ContractFields()
            return merged_once
        assert left == merged_once
        assert right == second_fields
        return merged_twice

    async def fake_summarize(
        received_client: StubClient,
        received_pages: list[Page],
    ) -> str:
        assert received_client is client
        assert received_pages == normalized_pages
        calls.append("summarize")
        return "summary"

    monkeypatch.setattr("sage.process.ensure_pdf", fake_ensure_pdf)
    monkeypatch.setattr("sage.process.detect_kind", fake_detect_kind)
    monkeypatch.setattr("sage.process.extract_text_pages", fake_extract_text_pages)
    monkeypatch.setattr("sage.process.ocr_pages", fake_ocr_pages)
    monkeypatch.setattr("sage.process.normalize_pages", fake_normalize_pages)
    monkeypatch.setattr("sage.process.chunk_pages", fake_chunk_pages)
    monkeypatch.setattr("sage.process.extract_one", fake_extract_one)
    monkeypatch.setattr("sage.process.summarize_chunk", fake_summarize_chunk)
    monkeypatch.setattr("sage.process.merge_fields", fake_merge_fields)
    monkeypatch.setattr("sage.process.summarize", fake_summarize)

    result = await process_document(src, tmp_path, llm_client=client)

    assert calls == [
        "ensure_pdf",
        "detect_kind",
        "extract_text_pages",
        "normalize_pages",
        "chunk_pages",
        "extract_one:0",
        "summarize_chunk:0",
        "merge_fields:42",
        "extract_one:1",
        "summarize_chunk:1",
        "merge_fields:none",
        "summarize",
    ]
    assert [chunk.chunk_summary for chunk in chunks] == ["summary 0", "summary 1"]
    assert result == ProcessingResult(
        chunks=chunks,
        fields=merged_twice,
        summary="summary",
        pages=normalized_pages,
        document_kind="text",
        partial=True,
        failed_chunk_indices=[1],
        preview_pdf_path=str(pdf_path),
    )


async def test_process_document_uses_ocr_for_scan_pdfs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    client = StubClient()
    pages = [Page(index=1, text="scan text", kind="scan")]

    async def fake_ensure_pdf(src: Path, work_dir: Path) -> Path:
        calls.append("ensure_pdf")
        return tmp_path / "scan.pdf"

    monkeypatch.setattr("sage.process.ensure_pdf", fake_ensure_pdf)
    monkeypatch.setattr("sage.process.detect_kind", lambda pdf_path: "scan")
    monkeypatch.setattr(
        "sage.process.extract_text_pages",
        lambda pdf_path: pytest.fail("extract_text_pages should not be called"),
    )

    def fake_ocr_pages(pdf_path: Path) -> list[Page]:
        calls.append("ocr_pages")
        return pages

    monkeypatch.setattr("sage.process.ocr_pages", fake_ocr_pages)
    monkeypatch.setattr("sage.process.normalize_pages", lambda received_pages: pages)
    monkeypatch.setattr("sage.process.chunk_pages", lambda received_pages: [])

    async def fake_summarize(client: StubClient, pages: list[Page]) -> str:
        return "summary"

    monkeypatch.setattr("sage.process.summarize", fake_summarize)

    result = await process_document(tmp_path / "scan.pdf", tmp_path, llm_client=client)

    assert calls == ["ensure_pdf", "ocr_pages"]
    assert result.document_kind == "scan"
    assert result.preview_pdf_path == str(tmp_path / "scan.pdf")
    assert result.pages == pages
    assert result.chunks == []
    assert result.fields == ContractFields()
    assert result.partial is False


async def test_process_document_creates_default_lm_studio_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    created: dict[str, str] = {}

    class FakeLMStudioClient:
        def __init__(self, base_url: str, model: str) -> None:
            created["base_url"] = base_url
            created["model"] = model

        async def __aenter__(self) -> "FakeLMStudioClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def chat(
            self,
            messages: list[dict[str, Any]],
            response_format: dict[str, Any] | None = None,
        ) -> str:
            raise NotImplementedError

    async def fake_ensure_pdf(src: Path, work_dir: Path) -> Path:
        return src

    async def fake_summarize(client: FakeLMStudioClient, pages: list[Page]) -> str:
        return ""

    monkeypatch.setenv("LM_STUDIO_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LM_STUDIO_LLM_MODEL", "local-model")
    monkeypatch.setattr("sage.process.LMStudioClient", FakeLMStudioClient)
    monkeypatch.setattr("sage.process.ensure_pdf", fake_ensure_pdf)
    monkeypatch.setattr("sage.process.detect_kind", lambda pdf_path: "text")
    monkeypatch.setattr("sage.process.extract_text_pages", lambda pdf_path: [])
    monkeypatch.setattr("sage.process.normalize_pages", lambda pages: [])
    monkeypatch.setattr("sage.process.chunk_pages", lambda pages: [])
    monkeypatch.setattr("sage.process.summarize", fake_summarize)

    result = await process_document(tmp_path / "source.pdf", tmp_path)

    assert created == {
        "base_url": "http://localhost:1234/v1",
        "model": "local-model",
    }
    assert result == ProcessingResult(
        chunks=[],
        fields=ContractFields(),
        summary="",
        pages=[],
        document_kind="text",
        partial=False,
        preview_pdf_path=str(tmp_path / "source.pdf"),
    )
