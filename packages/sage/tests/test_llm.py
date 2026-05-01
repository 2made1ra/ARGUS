import logging

import pytest
from sage.llm.extract import extract_one, merge_fields
from sage.llm.summary import summarize
from sage.models import Chunk, ContractFields, Page


class MockClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    async def chat(self, messages, response_format=None) -> str:
        self.calls.append(
            {
                "messages": messages,
                "response_format": response_format,
            }
        )
        return self.responses.pop(0)


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
    client = MockClient(['{"document_number":"42","supplier_name":"ООО Ромашка"}'])

    fields = await extract_one(client, make_chunk())

    assert fields == ContractFields(
        document_number="42",
        supplier_name="ООО Ромашка",
    )
    assert len(client.calls) == 1
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert "Запрещено выдумывать" in client.calls[0]["messages"][0]["content"]
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
            '{"document_number":{"bad":"shape"}}',
            '{"supplier_name":{"bad":"shape"}}',
        ]
    )

    with caplog.at_level(logging.WARNING):
        fields = await extract_one(client, make_chunk())

    assert fields == ContractFields()
    assert len(client.calls) == 2
    assert "extraction failed after retry" in caplog.text


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
    assert "1-2 предложения" in client.calls[0]["messages"][0]["content"]
    assert "Страница 1" in client.calls[0]["messages"][1]["content"]
    assert "Страница 2" in client.calls[1]["messages"][1]["content"]
    assert "не более 500 символов" in client.calls[2]["messages"][0]["content"]
    reduce_prompt = client.calls[2]["messages"][1]["content"]
    assert "На странице указаны стороны договора." in reduce_prompt
    assert "На странице указана стоимость услуг." in reduce_prompt
