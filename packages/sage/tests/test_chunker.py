from sage.chunker import chunk_pages
from sage.models import Page


def pages(*texts: str) -> list[Page]:
    return [Page(index=i, text=t, kind="text") for i, t in enumerate(texts, 1)]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_chunk_pages_empty_pages_returns_empty_chunks() -> None:
    assert chunk_pages([]) == []


def test_chunk_pages_all_blank_pages_returns_empty_chunks() -> None:
    assert chunk_pages(pages("", "   ", "")) == []


# ---------------------------------------------------------------------------
# Single-page splitting
# ---------------------------------------------------------------------------


def test_chunk_pages_splits_giant_page_respects_max_chars() -> None:
    long_text = "Alpha sentence. Beta sentence. Gamma sentence. Delta sentence."
    chunks = chunk_pages(pages(long_text), max_chars=25)

    texts = [c.text for c in chunks]
    assert all(len(t) <= 25 for t in texts), f"oversized chunk: {texts}"
    # All chunks are from the single page
    assert all(c.page_start == 1 and c.page_end == 1 for c in chunks)
    # chunk_index is sequential starting at 0
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    # Content round-trip: all source words are present somewhere
    combined = " ".join(texts)
    for word in ["Alpha", "Beta", "Gamma", "Delta"]:
        assert word in combined


def test_chunk_pages_single_page_within_max_chars_is_one_chunk() -> None:
    chunks = chunk_pages(pages("Short page text"), max_chars=2000)

    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].chunk_summary is None


def test_chunk_pages_long_page_all_chunks_on_same_page() -> None:
    long_text = "word " * 200  # 1000 chars
    chunks = chunk_pages(pages(long_text), max_chars=50)

    assert len(chunks) > 1
    assert all(c.page_start == 1 for c in chunks)
    assert all(c.page_end == 1 for c in chunks)


# ---------------------------------------------------------------------------
# Multi-page merging — key new behaviour of RCTS stream approach
# ---------------------------------------------------------------------------


def test_chunk_pages_merges_short_pages_into_single_chunk() -> None:
    chunks = chunk_pages(pages("First page body", "Second page body"), max_chars=2000)

    assert len(chunks) == 1
    assert "First page body" in chunks[0].text
    assert "Second page body" in chunks[0].text
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
    assert chunks[0].chunk_index == 0


def test_chunk_pages_cross_page_chunk_reports_correct_range() -> None:
    chunks = chunk_pages(pages("Hello", "World"), max_chars=20)

    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2


def test_chunk_pages_three_pages_merged_within_max_chars() -> None:
    chunks = chunk_pages(pages("Page one", "Page two", "Page three"), max_chars=2000)

    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 3


# ---------------------------------------------------------------------------
# Headings — split when max_chars forces it
# ---------------------------------------------------------------------------


def test_chunk_pages_headings_split_when_max_chars_forces_it() -> None:
    chunks = chunk_pages(pages("# First\n## Second\n### Third"), max_chars=10)

    texts = [c.text for c in chunks]
    assert texts == ["# First", "## Second", "### Third"]
    assert all(c.section_type == "header" for c in chunks)
    assert [c.chunk_index for c in chunks] == [0, 1, 2]


def test_chunk_pages_heading_chunk_section_type_is_header() -> None:
    chunks = chunk_pages(pages("# Section heading\nBody text follows here."), max_chars=20)

    header_chunks = [c for c in chunks if c.section_type == "header"]
    assert len(header_chunks) >= 1
    assert any("Section heading" in c.text for c in header_chunks)


def test_chunk_pages_body_chunk_section_type_is_body() -> None:
    chunks = chunk_pages(pages("Plain body text without any markdown headings."), max_chars=2000)

    assert len(chunks) == 1
    assert chunks[0].section_type == "body"


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_chunk_pages_preserves_page_range_invariant() -> None:
    source_pages = pages(
        "# First\nOne. Two. Three.",
        "Plain page body.",
        "# Last\nFour. Five.",
    )
    chunks = chunk_pages(source_pages, max_chars=12)

    assert chunks, "expected at least one chunk"
    assert all(c.page_start <= c.page_end for c in chunks)


def test_chunk_pages_chunk_index_is_sequential_from_zero() -> None:
    source_pages = pages("word " * 100)
    chunks = chunk_pages(source_pages, max_chars=50)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_pages_chunk_summary_is_always_none() -> None:
    chunks = chunk_pages(pages("Some text for testing."), max_chars=2000)

    assert all(c.chunk_summary is None for c in chunks)
