import logging

from pydantic import ValidationError

from sage.llm.client import LMStudioClient
from sage.models import Chunk, ContractFields

logger = logging.getLogger(__name__)

CONTRACT_FIELDS_SCHEMA = ", ".join(ContractFields.model_fields)

EXTRACT_SYSTEM_PROMPT = f"""Ты извлекаешь реквизиты и ключевые поля из русских
договоров и актов.
Верни только строгий JSON-объект без markdown, комментариев и пояснений.
JSON должен содержать только плоские поля модели ContractFields:
{CONTRACT_FIELDS_SCHEMA}.
Если значение поля отсутствует в тексте, укажи null.
Запрещено выдумывать значения, достраивать по смыслу, делать правдоподобные
догадки или брать данные не из текста.
Все найденные значения возвращай строками, без изменения смысла исходного документа."""

EXTRACT_USER_PROMPT_TEMPLATE = """Извлеки поля ContractFields из фрагмента документа.

Фрагмент:
{chunk_text}"""

EXTRACT_RETRY_PROMPT_TEMPLATE = """Предыдущий ответ не прошёл валидацию ContractFields.
Исправь ответ и верни только строгий JSON-объект.
Для отсутствующих значений используй null.
Не выдумывай и не угадывай значения.

Ошибка валидации:
{error}

Фрагмент:
{chunk_text}"""


async def extract_one(client: LMStudioClient, chunk: Chunk) -> ContractFields:
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": EXTRACT_USER_PROMPT_TEMPLATE.format(chunk_text=chunk.text),
        },
    ]

    last_error: ValidationError | None = None
    for attempt in range(2):
        raw = await client.chat(
            messages,
            response_format={"type": "json_object"},
        )
        try:
            return ContractFields.model_validate_json(raw)
        except ValidationError as error:
            last_error = error
            if attempt == 0:
                messages = [
                    {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": EXTRACT_RETRY_PROMPT_TEMPLATE.format(
                            error=str(error),
                            chunk_text=chunk.text,
                        ),
                    },
                ]

    logger.warning("ContractFields extraction failed after retry: %s", last_error)
    return ContractFields()


def merge_fields(left: ContractFields, right: ContractFields) -> ContractFields:
    return ContractFields(
        **{
            field_name: (
                left_value
                if (left_value := getattr(left, field_name)) is not None
                else getattr(right, field_name)
            )
            for field_name in ContractFields.model_fields
        }
    )
