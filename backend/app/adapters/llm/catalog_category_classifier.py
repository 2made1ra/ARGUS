from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import httpx

from app.core.domain.service_taxonomy import SERVICE_CATEGORIES
from app.features.catalog.entities.price_item import PriceItem
from app.features.catalog.ports import CatalogCategoryClassification


class CatalogCategoryClassifierResponseError(RuntimeError):
    pass


class LMStudioCatalogCategoryClassifier:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport

    async def classify(
        self,
        items: list[PriceItem],
    ) -> list[CatalogCategoryClassification]:
        if not items:
            return []

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        _items_payload(items),
                        ensure_ascii=False,
                    ),
                },
            ],
            "max_tokens": 2048,
            "temperature": 0,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "argus_catalog_category_classifier",
                    "strict": True,
                    "schema": _json_schema(),
                },
            },
        }
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(self._chat_completions_url(), json=payload)
            response.raise_for_status()
        return _classifications_from_content(_content_from_response(response.json()))

    def _chat_completions_url(self) -> str:
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        return f"{self._base_url}/chat/completions"


def _items_payload(items: list[PriceItem]) -> dict[str, object]:
    return {
        "allowed_service_categories": list(SERVICE_CATEGORIES),
        "items": [
            {
                "id": str(item.id),
                "name": item.name,
                "source_category": item.category,
                "section": item.section,
                "source_text": item.source_text,
                "unit": item.unit_normalized or item.unit,
            }
            for item in items
        ],
    }


def _system_prompt() -> str:
    return (
        "Classify catalog price rows into one allowed service category. "
        "Use only the provided row fields. Do not invent supplier facts, prices, "
        "or SQL. Return JSON matching the schema exactly."
    )


def _json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "service_category": {
                            "type": "string",
                            "enum": list(SERVICE_CATEGORIES),
                        },
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": ["string", "null"]},
                    },
                    "required": ["id", "service_category", "confidence", "reason"],
                },
            },
        },
        "required": ["items"],
    }


def _content_from_response(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise CatalogCategoryClassifierResponseError(
            "Unexpected catalog category classifier response shape",
        ) from exc
    return str(content).strip()


def _classifications_from_content(content: str) -> list[CatalogCategoryClassification]:
    try:
        payload = json.loads(content)
        items = payload["items"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CatalogCategoryClassifierResponseError(
            "Invalid catalog category classifier JSON",
        ) from exc

    classifications: list[CatalogCategoryClassification] = []
    for item in items:
        try:
            classifications.append(
                CatalogCategoryClassification(
                    item_id=UUID(str(item["id"])),
                    service_category=str(item["service_category"]),
                    confidence=float(item["confidence"]),
                    reason=item.get("reason"),
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CatalogCategoryClassifierResponseError(
                "Invalid catalog category classifier item",
            ) from exc
    return classifications


__all__ = [
    "CatalogCategoryClassifierResponseError",
    "LMStudioCatalogCategoryClassifier",
]
