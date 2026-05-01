from sage import Chunk, ContractFields, ExtractedDocument, Page, ProcessingResult


def test_page_model_dump() -> None:
    page = Page(index=1, text="Contract text", kind="text")

    assert page.model_dump() == {
        "index": 1,
        "text": "Contract text",
        "kind": "text",
    }


def test_chunk_model_dump_includes_optional_none() -> None:
    chunk = Chunk(
        text="Chunk text",
        page_start=1,
        page_end=2,
        section_type=None,
        chunk_index=0,
        chunk_summary=None,
    )

    assert chunk.model_dump() == {
        "text": "Chunk text",
        "page_start": 1,
        "page_end": 2,
        "section_type": None,
        "chunk_index": 0,
        "chunk_summary": None,
    }


def test_contract_fields_model_dump_defaults_to_none() -> None:
    fields = ContractFields()

    assert fields.model_dump() == {
        "document_type": None,
        "document_number": None,
        "document_date": None,
        "supplier_name": None,
        "customer_name": None,
        "service_date": None,
        "amount": None,
        "vat": None,
        "valid_until": None,
        "supplier_inn": None,
        "supplier_kpp": None,
        "supplier_bik": None,
        "supplier_account": None,
        "customer_inn": None,
        "customer_kpp": None,
        "customer_bik": None,
        "customer_account": None,
        "service_subject": None,
        "service_price": None,
        "signatory_name": None,
        "contact_phone": None,
    }


def test_extracted_document_model_dump() -> None:
    page = Page(index=1, text="Contract text", kind="text")
    chunk = Chunk(
        text="Chunk text",
        page_start=1,
        page_end=1,
        section_type=None,
        chunk_index=0,
        chunk_summary=None,
    )
    extracted = ExtractedDocument(pages=[page], document_kind="text", chunks=[chunk])

    assert extracted.model_dump() == {
        "pages": [page.model_dump()],
        "document_kind": "text",
        "chunks": [chunk.model_dump()],
    }


def test_processing_result_model_dump() -> None:
    page = Page(index=1, text="Contract text", kind="text")
    chunk = Chunk(
        text="Chunk text",
        page_start=1,
        page_end=1,
        section_type=None,
        chunk_index=0,
        chunk_summary=None,
    )
    fields = ContractFields()
    result = ProcessingResult(
        chunks=[chunk],
        fields=fields,
        summary="Short summary",
        pages=[page],
        document_kind="text",
        partial=False,
    )

    assert result.model_dump() == {
        "chunks": [chunk.model_dump()],
        "fields": fields.model_dump(),
        "summary": "Short summary",
        "pages": [page.model_dump()],
        "document_kind": "text",
        "partial": False,
    }
