import json
import logging
from typing import Any

import httpx
import pytest
from sage.llm.client import LMStudioClient
from sage.llm.extract import extract_one, merge_fields
from sage.llm.summary import summarize, summarize_chunk
from sage.models import Chunk, ContractFields, Page


class MockClient:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        self.calls.append(
            {
                "messages": messages,
                "response_format": response_format,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_chunk(text: str = "Договор N 42 от 01.02.2024") -> Chunk:
    return Chunk(
        text=text,
        page_start=1,
        page_end=1,
        section_type=None,
        chunk_index=0,
        chunk_summary=None,
    )


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (ContractFields(), ContractFields(), ContractFields()),
        (
            ContractFields(document_number="L"),
            ContractFields(document_number="R"),
            ContractFields(document_number="L"),
        ),
        (
            ContractFields(document_number=None),
            ContractFields(document_number="R"),
            ContractFields(document_number="R"),
        ),
        (
            ContractFields(document_number=""),
            ContractFields(document_number="R"),
            ContractFields(document_number="R"),
        ),
        (
            ContractFields(supplier_name="Поставщик"),
            ContractFields(customer_name="Заказчик"),
            ContractFields(supplier_name="Поставщик", customer_name="Заказчик"),
        ),
        (
            ContractFields(amount="1000", vat=None),
            ContractFields(amount=None, vat="200"),
            ContractFields(amount="1000", vat="200"),
        ),
        (
            ContractFields(supplier_inn=None, supplier_kpp="770101001"),
            ContractFields(supplier_inn="7701000000", supplier_kpp="ignored"),
            ContractFields(supplier_inn="7701000000", supplier_kpp="770101001"),
        ),
        (
            ContractFields(service_subject="Услуги", service_price=None),
            ContractFields(service_subject="Работы", service_price="500"),
            ContractFields(service_subject="Услуги", service_price="500"),
        ),
        (
            ContractFields(contact_phone=None, signatory_name="Иванов И.И."),
            ContractFields(contact_phone="+7 000", signatory_name=None),
            ContractFields(contact_phone="+7 000", signatory_name="Иванов И.И."),
        ),
    ],
)
def test_merge_fields_left_prefer(
    left: ContractFields,
    right: ContractFields,
    expected: ContractFields,
) -> None:
    assert merge_fields(left, right) == expected


async def test_extract_one_succeeds_first_try() -> None:
    client = MockClient(
        ['```json\n{"document_number":"42","supplier_name":"ООО Ромашка"}\n```']
    )

    fields = await extract_one(client, make_chunk())

    assert fields == ContractFields(
        document_number="42",
        supplier_name="ООО Ромашка",
    )
    assert len(client.calls) == 1
    assert client.calls[0]["response_format"] is None
    assert "Не выдумывай" in client.calls[0]["messages"][0]["content"]
    assert "null" in client.calls[0]["messages"][0]["content"]


async def test_extract_one_retries_on_validation_error() -> None:
    client = MockClient(
        [
            '{"document_number":{"bad":"shape"}}',
            '{"document_number":"42"}',
        ]
    )

    fields = await extract_one(client, make_chunk())

    assert fields == ContractFields(document_number="42")
    assert len(client.calls) == 2
    assert "Ошибка валидации" in client.calls[1]["messages"][1]["content"]
    assert "Не выдумывай" in client.calls[1]["messages"][1]["content"]


async def test_extract_one_falls_back_after_two_validation_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = MockClient(
        [
            "Модель ответила так: {bad json}",
            '{"supplier_name":{"bad":"shape"}}',
        ]
    )

    with caplog.at_level(logging.WARNING):
        fields = await extract_one(client, make_chunk())

    assert fields == ContractFields()
    assert len(client.calls) == 2
    assert "extraction failed after retry" in caplog.text


async def test_extract_one_uses_native_chat_json_when_available() -> None:
    class JsonClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def chat_json(self, system: str, user: str) -> dict[str, Any]:
            self.calls.append((system, user))
            return {"document_number": "42"}

        async def chat(
            self,
            messages: list[dict[str, Any]],
            response_format: dict[str, Any] | None = None,
        ) -> str:
            raise AssertionError("chat should not be called when chat_json exists")

    client = JsonClient()

    fields = await extract_one(client, make_chunk())

    assert fields == ContractFields(document_number="42")
    assert len(client.calls) == 1


async def test_summarize_uses_map_reduce_chain() -> None:
    client = MockClient(
        [
            "На странице указаны стороны договора.",
            "На странице указана стоимость услуг.",
            "Договор на оказание услуг между сторонами со стоимостью услуг.",
        ]
    )
    pages = [
        Page(index=1, text="Исполнитель ООО Ромашка", kind="text"),
        Page(index=2, text="Цена услуг 1000 рублей", kind="text"),
    ]

    summary = await summarize(client, pages)

    assert summary == "Договор на оказание услуг между сторонами со стоимостью услуг."
    assert len(client.calls) == 3
    assert "1-2 предложения" in client.calls[0]["messages"][1]["content"]
    assert "Страница 1" in client.calls[0]["messages"][1]["content"]
    assert "Страница 2" in client.calls[1]["messages"][1]["content"]
    assert "не более 500 символов" in client.calls[2]["messages"][1]["content"]
    reduce_prompt = client.calls[2]["messages"][1]["content"]
    assert "На странице указаны стороны договора." in reduce_prompt
    assert "На странице указана стоимость услуг." in reduce_prompt


async def test_summarize_skips_failed_pages_and_single_reduce(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = MockClient([RuntimeError("map failed"), "Краткое содержание второй."])
    pages = [
        Page(index=1, text="Первый текст", kind="text"),
        Page(index=2, text="Второй текст", kind="text"),
        Page(index=3, text="   ", kind="text"),
    ]

    with caplog.at_level(logging.WARNING):
        summary = await summarize(client, pages)

    assert summary == "Страница 2: Краткое содержание второй."
    assert len(client.calls) == 2
    assert "page 1 summary failed" in caplog.text


async def test_summarize_returns_page_concatenation_when_reduce_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = MockClient(
        [
            "Содержание первой.",
            "Содержание второй.",
            RuntimeError("reduce failed"),
        ]
    )
    pages = [
        Page(index=1, text="Первый текст", kind="text"),
        Page(index=2, text="Второй текст", kind="text"),
    ]

    with caplog.at_level(logging.WARNING):
        summary = await summarize(client, pages)

    assert summary == "Страница 1: Содержание первой. Страница 2: Содержание второй."
    assert len(client.calls) == 3
    assert "reduce summary failed" in caplog.text


async def test_summarize_chunk_sets_payload_summary() -> None:
    client = MockClient(["Краткое содержание фрагмента."])

    summary = await summarize_chunk(client, make_chunk("Предмет договора - услуги."))

    assert summary == "Краткое содержание фрагмента."
    assert len(client.calls) == 1
    assert "Фрагмент 0" in client.calls[0]["messages"][1]["content"]


async def test_summarize_chunk_returns_none_on_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = MockClient([RuntimeError("chunk summary failed")])

    with caplog.at_level(logging.WARNING):
        summary = await summarize_chunk(client, make_chunk("Текст"))

    assert summary is None
    assert "chunk 0 summary failed" in caplog.text


async def test_lmstudio_client_retries_without_response_format_on_400() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = dict(json.loads(request.content))
        requests.append(payload)
        if "response_format" in payload:
            return httpx.Response(400, json={"error": "response_format unsupported"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"document_number":"42"}'}}]},
        )

    transport = httpx.MockTransport(handler)

    async with LMStudioClient(
        "http://lmstudio.test/v1",
        "google/gemma-4-4b",
        transport=transport,
    ) as client:
        content = await client.chat(
            [{"role": "user", "content": "Верни JSON"}],
            response_format={"type": "json_object"},
        )

    assert content == '{"document_number":"42"}'
    assert len(requests) == 2
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in requests[1]


async def test_lmstudio_client_chat_json_uses_loose_parser() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = dict(json.loads(request.content))
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                'Вот JSON:\n```json\n{"document_number":"42"}\n```'
                            )
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    async with LMStudioClient(
        "http://lmstudio.test/v1",
        "google/gemma-4-4b",
        transport=transport,
    ) as client:
        content = await client.chat_json("system", "user")

    assert content == {"document_number": "42"}
    assert len(requests) == 1
    assert "response_format" not in requests[0]
