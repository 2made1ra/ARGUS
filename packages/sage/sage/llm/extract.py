import logging
from typing import Any

from pydantic import ValidationError

from sage.llm.client import ChatClient, LLMError, parse_json_loose
from sage.llm.prompts import (
    SYSTEM_EXTRACT,
    build_extract_retry_user,
    build_extract_user,
)
from sage.models import Chunk, ContractFields

logger = logging.getLogger(__name__)


async def extract_one(client: ChatClient, chunk: Chunk) -> ContractFields:
    user_prompt = build_extract_user(chunk.text)
    last_error: ValidationError | LLMError | None = None
    for attempt in range(2):
        try:
            raw = await _chat_json(client, SYSTEM_EXTRACT, user_prompt)
            return ContractFields.model_validate(raw)
        except (ValidationError, LLMError) as error:
            last_error = error
            if attempt == 0:
                user_prompt = build_extract_retry_user(chunk.text, str(error))

    logger.warning("ContractFields extraction failed after retry: %s", last_error)
    return ContractFields()


def merge_fields(left: ContractFields, right: ContractFields) -> ContractFields:
    return ContractFields(
        **{
            field_name: (
                left_value
                if (left_value := getattr(left, field_name)) not in (None, "")
                else getattr(right, field_name)
            )
            for field_name in ContractFields.model_fields
        }
    )


async def _chat_json(
    client: ChatClient,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    chat_json = getattr(client, "chat_json", None)
    if callable(chat_json):
        result = await chat_json(system_prompt, user_prompt)
        if isinstance(result, dict):
            return result
        raise LLMError(f"LLM JSON response must be object, got {type(result).__name__}")

    raw = await client.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return parse_json_loose(raw)
