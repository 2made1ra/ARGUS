from typing import Literal, Optional

from pydantic import BaseModel


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
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    document_date: Optional[str] = None
    supplier_name: Optional[str] = None
    customer_name: Optional[str] = None
    service_date: Optional[str] = None
    amount: Optional[str] = None
    vat: Optional[str] = None
    valid_until: Optional[str] = None
    supplier_inn: Optional[str] = None
    supplier_kpp: Optional[str] = None
    supplier_bik: Optional[str] = None
    supplier_account: Optional[str] = None
    customer_inn: Optional[str] = None
    customer_kpp: Optional[str] = None
    customer_bik: Optional[str] = None
    customer_account: Optional[str] = None
    service_subject: Optional[str] = None
    service_price: Optional[str] = None
    signatory_name: Optional[str] = None
    contact_phone: Optional[str] = None


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
