from typing import Literal

from pydantic import BaseModel, Field


class Page(BaseModel):
    index: int
    text: str
    kind: Literal["text", "scan"]


class Chunk(BaseModel):
    text: str
    page_start: int
    page_end: int
    section_type: str | None = None
    chunk_index: int
    chunk_summary: str | None = None


class ContractFields(BaseModel):
    document_type: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    supplier_name: str | None = None
    customer_name: str | None = None
    service_date: str | None = None
    amount: str | None = None
    vat: str | None = None
    valid_until: str | None = None
    supplier_inn: str | None = None
    supplier_kpp: str | None = None
    supplier_bik: str | None = None
    supplier_account: str | None = None
    customer_inn: str | None = None
    customer_kpp: str | None = None
    customer_bik: str | None = None
    customer_account: str | None = None
    service_subject: str | None = None
    service_price: str | None = None
    signatory_name: str | None = None
    contact_phone: str | None = None


class ExtractedDocument(BaseModel):
    pages: list[Page]
    document_kind: Literal["text", "scan"]
    chunks: list[Chunk]


class ProcessingResult(BaseModel):
    chunks: list[Chunk]
    fields: ContractFields
    summary: str
    pages: list[Page]
    document_kind: Literal["text", "scan"]
    partial: bool
    failed_chunk_indices: list[int] = Field(default_factory=list)
    preview_pdf_path: str | None = None
