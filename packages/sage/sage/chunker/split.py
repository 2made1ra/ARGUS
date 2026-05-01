import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from sage.models import Chunk, Page

_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


@dataclass(frozen=True)
class _PageOffset:
    char_start: int
    page_index: int


def chunk_pages(pages: list[Page], max_chars: int = 2000) -> list[Chunk]:
    """Split normalized document pages into text chunks.

    All page texts are concatenated into one stream and split by
    RecursiveCharacterTextSplitter. Each chunk's page_start/page_end
    is recovered from a character-offset table, so sections that span
    page boundaries get accurate metadata.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be greater than 0")

    non_empty = [p for p in pages if p.text]
    if not non_empty:
        return []

    # Phase 1: build combined string + offset table
    offsets: list[_PageOffset] = []
    cursor = 0
    segments: list[str] = []
    for page in non_empty:
        offsets.append(_PageOffset(char_start=cursor, page_index=page.index))
        segments.append(page.text)
        cursor += len(page.text) + 2  # +2 for the "\n\n" separator

    combined = "\n\n".join(segments)

    # Phase 2: split with RCTS
    raw_chunks = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=0,
        separators=_SEPARATORS,
    ).split_text(combined)

    if not raw_chunks:
        return []

    # Phase 3: map chunk positions back to page indices
    result: list[Chunk] = []
    search_start = 0
    for chunk_index, chunk_text in enumerate(raw_chunks):
        char_start = combined.index(chunk_text, search_start)
        char_end = char_start + len(chunk_text) - 1
        search_start = char_start + 1

        result.append(Chunk(
            text=chunk_text,
            page_start=_page_for_offset(char_start, offsets),
            page_end=_page_for_offset(char_end, offsets),
            section_type=_section_type(chunk_text),
            chunk_index=chunk_index,
            chunk_summary=None,
        ))

    return result


def _page_for_offset(offset: int, offsets: list[_PageOffset]) -> int:
    """Return the page_index whose range contains the given character offset."""
    result = offsets[0].page_index
    for entry in offsets:
        if entry.char_start <= offset:
            result = entry.page_index
        else:
            break
    return result


def _section_type(text: str) -> str:
    return "header" if _HEADING_RE.match(text) else "body"
