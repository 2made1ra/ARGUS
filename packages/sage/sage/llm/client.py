from typing import Any

import httpx


class LMStudioClient:
    def __init__(self, base_url: str, model: str, *, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "LMStudioClient":
        self._http = httpx.AsyncClient(timeout=self.timeout)
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
            raise RuntimeError("LMStudioClient must be used as an async context manager")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        response = await self._http.post(self._chat_completions_url(), json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return str(content)

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"
