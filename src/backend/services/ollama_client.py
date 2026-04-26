import asyncio
import json
import os
from typing import AsyncIterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.services.circuit_breaker import circuit_breaker


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 20.0) -> None:
        self.base_url = base_url or f"http://{os.getenv('OLLAMA_HOST', 'localhost')}:{os.getenv('OLLAMA_PORT', '11434')}"
        self.timeout = timeout

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            return response

    async def _get_json(self, path: str) -> dict | list:
        response = await self._request("GET", path)
        return response.json()

    @retry(wait=wait_exponential(min=0.2, max=2), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    async def list_models(self) -> list[dict]:
        if not circuit_breaker.allow():
            raise httpx.HTTPError("Ollama circuit breaker open")

        try:
            data = await self._get_json("/api/models")
            circuit_breaker.record_success()
            if isinstance(data, dict):
                return data.get("models") or data.get("tags") or data.get("items") or []
            return data
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                fallback = await self._get_json("/api/tags")
                if isinstance(fallback, dict):
                    return fallback.get("models") or fallback.get("tags") or fallback.get("items") or []
                return fallback
            circuit_breaker.record_failure()
            raise
        except httpx.HTTPError:
            circuit_breaker.record_failure()
            raise

    @retry(wait=wait_exponential(min=0.2, max=2), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    async def list_running(self) -> list[dict]:
        if not circuit_breaker.allow():
            raise httpx.HTTPError("Ollama circuit breaker open")

        try:
            data = await self._get_json("/api/ps")
            circuit_breaker.record_success()
            if isinstance(data, dict):
                return data.get("models") or data.get("processes") or []
            return data
        except httpx.HTTPError:
            circuit_breaker.record_failure()
            return []

    async def chat_stream(self, model: str, messages: list[dict], options: dict | None = None) -> AsyncIterator[str]:
        if not circuit_breaker.allow():
            raise httpx.HTTPError("Ollama circuit breaker open")

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options or {},
        }

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                circuit_breaker.record_success()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if isinstance(data, dict) and data.get("message") and isinstance(data["message"], dict):
                        content = data["message"].get("content")
                        if content is not None:
                            yield content

    async def pull_model(self, model: str) -> AsyncIterator[dict]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/pull", json={"name": model}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield json.loads(line)

    async def stop_model(self, model: str) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await client.post(f"{self.base_url}/api/stop", json={"name": model})
