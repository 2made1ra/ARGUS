from sage.models import (
    Chunk,
    ContractFields,
    ExtractedDocument,
    Page,
    ProcessingResult,
)


def __getattr__(name: str) -> object:
    if name == "process_document":
        from sage.process import process_document

        return process_document
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Chunk",
    "ContractFields",
    "ExtractedDocument",
    "Page",
    "ProcessingResult",
    "process_document",
]
