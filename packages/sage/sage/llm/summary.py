import asyncio

from sage.llm.client import LMStudioClient
from sage.models import Page

SUMMARY_MAP_SYSTEM_PROMPT = """Ты кратко пересказываешь страницы русских договоров.
Верни только краткое содержание страницы в 1-2 предложения.
Не добавляй факты, которых нет в тексте, и не делай правдоподобные догадки."""

SUMMARY_MAP_USER_PROMPT_TEMPLATE = """Составь краткое содержание страницы документа.

Страница {page_index}:
{page_text}"""

SUMMARY_REDUCE_SYSTEM_PROMPT = """Ты объединяешь краткие содержания страниц
русского договора.
Верни только итоговое краткое содержание всего документа на русском языке.
Ограничение: не более 500 символов.
Не добавляй факты, которых нет в кратких содержаниях, и не делай правдоподобные
догадки."""

SUMMARY_REDUCE_USER_PROMPT_TEMPLATE = """Объедини краткие содержания страниц в
одно summary документа.

Краткие содержания:
{page_summaries}"""


async def summarize(client: LMStudioClient, pages: list[Page]) -> str:
    if not pages:
        return ""

    async def _map_page(page: Page) -> str:
        result = await client.chat([
            {"role": "system", "content": SUMMARY_MAP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": SUMMARY_MAP_USER_PROMPT_TEMPLATE.format(
                    page_index=page.index,
                    page_text=page.text,
                ),
            },
        ])
        return f"Страница {page.index}: {result}"

    page_summaries: list[str] = await asyncio.gather(*(_map_page(p) for p in pages))

    return await client.chat([
        {"role": "system", "content": SUMMARY_REDUCE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": SUMMARY_REDUCE_USER_PROMPT_TEMPLATE.format(
                page_summaries="\n".join(page_summaries),
            ),
        },
    ])
