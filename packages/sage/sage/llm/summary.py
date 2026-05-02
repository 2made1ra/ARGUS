import logging

from sage.llm.client import ChatClient
from sage.llm.prompts import (
    SYSTEM_SUMMARY,
    build_chunk_summary_user,
    build_map_summary_user,
    build_reduce_summary_user,
)
from sage.models import Chunk, Page

logger = logging.getLogger(__name__)


async def summarize(client: ChatClient, pages: list[Page]) -> str:
    if not pages:
        return ""

    page_summaries: list[str] = []
    for page in pages:
        if not page.text.strip():
            continue
        try:
            result = await client.chat(
                [
                    {"role": "system", "content": SYSTEM_SUMMARY},
                    {
                        "role": "user",
                        "content": build_map_summary_user(page.text, page.index),
                    },
                ]
            )
        except Exception as exc:
            logger.warning("page %s summary failed: %s", page.index, exc)
            continue
        page_summaries.append(f"Страница {page.index}: {result.strip()}")

    if not page_summaries:
        return ""
    if len(page_summaries) == 1:
        return page_summaries[0]

    try:
        return (
            await client.chat(
                [
                    {"role": "system", "content": SYSTEM_SUMMARY},
                    {
                        "role": "user",
                        "content": build_reduce_summary_user(page_summaries),
                    },
                ]
            )
        ).strip()
    except Exception as exc:
        logger.warning("reduce summary failed: %s; returning concatenation", exc)
        return " ".join(page_summaries)


async def summarize_chunk(client: ChatClient, chunk: Chunk) -> str | None:
    if not chunk.text.strip():
        return None

    try:
        result = await client.chat(
            [
                {"role": "system", "content": SYSTEM_SUMMARY},
                {
                    "role": "user",
                    "content": build_chunk_summary_user(
                        chunk.text,
                        chunk.chunk_index,
                    ),
                },
            ]
        )
    except Exception as exc:
        logger.warning("chunk %s summary failed: %s", chunk.chunk_index, exc)
        return None

    summary = result.strip()
    return summary or None
