from sage.models import ContractFields

_FIELDS_SCHEMA = "\n".join(
    f'  "{field_name}": <строка или null>' for field_name in ContractFields.model_fields
)

SYSTEM_EXTRACT = (
    "Ты извлекаешь реквизиты и ключевые поля из русских договоров и актов. "
    "Отвечай только строгим JSON-объектом по заданной схеме, без markdown, "
    "комментариев и пояснений. Если поле отсутствует в тексте, укажи null. "
    "Не выдумывай значения, не достраивай по смыслу и не делай догадки."
)

SYSTEM_SUMMARY = (
    "Ты составляешь краткое резюме российских договоров. Отвечай кратко, "
    "на русском языке, без вступлений. Не добавляй факты, которых нет в тексте."
)


def build_extract_user(chunk_text: str) -> str:
    return (
        "Извлеки поля ContractFields из следующего фрагмента документа.\n\n"
        f"Схема ответа, строго JSON:\n{{\n{_FIELDS_SCHEMA}\n}}\n\n"
        f"Фрагмент:\n{chunk_text}"
    )


def build_extract_retry_user(chunk_text: str, validation_error: str) -> str:
    return (
        f"{build_extract_user(chunk_text)}\n\n"
        "Предыдущий ответ не прошёл валидацию ContractFields.\n"
        f"Ошибка валидации:\n{validation_error}\n\n"
        "Исправь ответ и верни ровно JSON по схеме, без пояснений. "
        "Для отсутствующих значений используй null. Не выдумывай и не угадывай."
    )


def build_map_summary_user(page_text: str, page_index: int) -> str:
    return (
        "Составь краткое содержание страницы документа в 1-2 предложения.\n\n"
        f"Страница {page_index}:\n{page_text}"
    )


def build_reduce_summary_user(page_summaries: list[str]) -> str:
    joined = "\n".join(f"- {summary}" for summary in page_summaries)
    return (
        f"Вот краткие содержания страниц договора:\n{joined}\n\n"
        "Составь итоговое summary всего документа на русском языке. "
        "Ограничение: не более 500 символов."
    )


def build_chunk_summary_user(chunk_text: str, chunk_index: int) -> str:
    return (
        "Составь краткое содержание фрагмента договора в 1 предложение.\n\n"
        f"Фрагмент {chunk_index}:\n{chunk_text}"
    )
