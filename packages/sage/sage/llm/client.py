import json
import re
from typing import Any, Protocol

import httpx


class LLMError(RuntimeError):
    pass


class ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> str: ...


class LMStudioClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._transport = transport
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "LMStudioClient":
        self._http = httpx.AsyncClient(timeout=self.timeout, transport=self._transport)
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        if self._http is None:
            raise RuntimeError(
                "LMStudioClient must be used as an async context manager"
            )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        response = await self._post_chat(payload)
        if response.status_code == 400 and response_format is not None:
            payload.pop("response_format")
            response = await self._post_chat(payload)
        if response.status_code >= 400:
            raise LLMError(
                f"LM Studio HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMError(
                f"Unexpected LM Studio response shape: {response.text[:300]}"
            ) from exc
        return str(content)

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        raw = await self.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        return parse_json_loose(raw)

    async def _post_chat(self, payload: dict[str, Any]) -> httpx.Response:
        if self._http is None:
            raise RuntimeError(
                "LMStudioClient must be used as an async context manager"
            )
        try:
            return await self._http.post(self._chat_completions_url(), json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"LM Studio request failed: {exc}") from exc

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_FIRST_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_loose(raw: str) -> dict[str, Any]:
    """Parse local-LLM JSON even when it is wrapped in prose or markdown fences."""
    stripped = raw.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    fence_match = _JSON_FENCE.search(stripped)
    if fence_match is not None:
        try:
            parsed = json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    object_match = _FIRST_OBJECT.search(stripped)
    if object_match is not None:
        try:
            parsed = json.loads(object_match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(
                f"Could not parse JSON from LLM response: {raw[:300]}"
            ) from exc
        if isinstance(parsed, dict):
            return parsed

    raise LLMError(f"Could not parse JSON from LLM response: {raw[:300]}")
