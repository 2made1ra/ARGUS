from __future__ import annotations

from collections.abc import Iterable

from app.features.search.dto import ChatMessage, RagContextChunk

SYSTEM_GROUNDED_RAG = """\
Ты — помощник ARGUS для анализа договоров и подрядчиков.
Отвечай только на русском языке и только по предоставленному контексту.
Не выдумывай подрядчиков, условия, суммы, даты, риски или выводы.
Если контекста недостаточно, прямо скажи: "В загруженных документах недостаточно данных для ответа".
Когда используешь факт из контекста, ссылайся на источник в формате [S1], [S2].
Ответ должен быть кратким, деловым и полезным для пользователя.
"""


def build_global_answer_messages(
    *,
    message: str,
    contexts: list[RagContextChunk],
    history: list[ChatMessage],
) -> list[ChatMessage]:
    user = (
        "Задача: найти подходящих подрядчиков по запросу пользователя и кратко "
        "объяснить, почему они подходят.\n\n"
        f"Запрос пользователя: {message}\n\n"
        f"Контекст:\n{_format_contexts(contexts)}"
    )
    return _messages(user=user, history=history)


def build_contractor_answer_messages(
    *,
    message: str,
    contractor_name: str,
    document_count: int,
    contexts: list[RagContextChunk],
    history: list[ChatMessage],
) -> list[ChatMessage]:
    user = (
        "Задача: ответить по конкретному подрядчику на основании его договоров.\n\n"
        f"Подрядчик: {contractor_name}\n"
        f"Количество договоров в базе: {document_count}\n"
        f"Вопрос пользователя: {message}\n\n"
        f"Контекст:\n{_format_contexts(contexts)}"
    )
    return _messages(user=user, history=history)


def build_document_answer_messages(
    *,
    message: str,
    document_title: str,
    summary: str | None,
    fields: dict[str, object],
    contexts: list[RagContextChunk],
    history: list[ChatMessage],
) -> list[ChatMessage]:
    facts = _format_fields(fields)
    user = (
        "Задача: ответить по содержанию одного выбранного договора.\n\n"
        f"Документ: {document_title}\n"
        f"Summary документа: {summary or 'нет'}\n"
        f"Извлеченные поля:\n{facts}\n\n"
        f"Вопрос пользователя: {message}\n\n"
        f"Контекст:\n{_format_contexts(contexts)}"
    )
    return _messages(user=user, history=history)


def _messages(*, user: str, history: list[ChatMessage]) -> list[ChatMessage]:
    bounded_history = [
        item
        for item in history[-6:]
        if item.role in {"user", "assistant"} and item.content.strip()
    ]
    return [
        ChatMessage(role="system", content=SYSTEM_GROUNDED_RAG),
        *bounded_history,
        ChatMessage(role="user", content=user),
    ]


def _format_contexts(contexts: Iterable[RagContextChunk]) -> str:
    lines: list[str] = []
    for context in contexts:
        source = context.source
        page = _format_pages(source.page_start, source.page_end)
        document = source.document_title or str(source.document_id)
        contractor = source.contractor_name or "не указан"
        lines.append(
            "\n".join(
                [
                    f"[S{context.source_index}]",
                    f"Подрядчик: {contractor}",
                    f"Документ: {document}",
                    f"Страницы: {page}",
                    f"Chunk: {source.chunk_index}",
                    f"Текст: {context.text}",
                ],
            ),
        )
    return "\n\n".join(lines) if lines else "нет релевантного контекста"


def _format_pages(start: int | None, end: int | None) -> str:
    if start is None and end is None:
        return "не указаны"
    if start == end or end is None:
        return str(start)
    if start is None:
        return str(end)
    return f"{start}-{end}"


def _format_fields(fields: dict[str, object]) -> str:
    present = [
        f"- {key}: {value}"
        for key, value in fields.items()
        if value is not None and value != ""
    ]
    return "\n".join(present) if present else "нет"


__all__ = [
    "SYSTEM_GROUNDED_RAG",
    "build_contractor_answer_messages",
    "build_document_answer_messages",
    "build_global_answer_messages",
]
