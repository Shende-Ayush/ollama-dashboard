import asyncio
import json
import os
from typing import AsyncIterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.services.circuit_breaker import circuit_breaker


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 20.0) -> None:
        host = os.getenv("OLLAMA_HOST", "ollama")  # 🔥 FIXED DEFAULT
        port = os.getenv("OLLAMA_PORT", "11434")

        self.base_url = base_url or f"http://{host}:{port}"
        self.timeout = timeout

        # 🔥 Reuse client (connection pooling)
        self.client = httpx.AsyncClient(timeout=self.timeout)

    # -------------------------------
    # CORE REQUEST
    # -------------------------------
    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = await self.client.request(method, f"{self.base_url}{path}", **kwargs)
        response.raise_for_status()
        return response

    async def _get_json(self, path: str) -> dict | list:
        response = await self._request("GET", path)
        return response.json()

    # -------------------------------
    # MODELS
    # -------------------------------
    @retry(wait=wait_exponential(min=0.2, max=2), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    async def list_models(self) -> list[dict]:
        if not circuit_breaker.allow():
            raise httpx.HTTPError("Circuit breaker open")

        try:
            data = await self._get_json("/api/tags")  # 🔥 more reliable than /models
            circuit_breaker.record_success()
            return data.get("models") or data.get("tags") or []
        except httpx.HTTPError:
            circuit_breaker.record_failure()
            raise

    async def model_exists(self, model: str) -> bool:
        models = await self.list_models()
        return any(m.get("name") == model for m in models)

    # -------------------------------
    # RUNNING MODELS
    # -------------------------------
    async def list_running(self) -> list[dict]:
        try:
            data = await self._get_json("/api/ps")
            return data.get("models") or data.get("processes") or []
        except Exception:
            return []

    # -------------------------------
    # STOP MODEL (STRONG)
    # -------------------------------
    async def stop_model(self, model: str) -> None:
        try:
            await self._request("POST", "/api/stop", json={"name": model})
        except Exception:
            pass

        # 🔥 ensure it's actually stopped
        for _ in range(5):
            running = await self.list_running()
            if not any(m.get("name") == model for m in running):
                return
            await asyncio.sleep(0.5)

    # -------------------------------
    # DELETE MODEL (🔥 KEY FIX)
    # -------------------------------
    async def delete_model(self, model: str) -> None:
        # Step 1: stop
        await self.stop_model(model)

        # Step 2: ensure exists
        if not await self.model_exists(model):
            raise ValueError(f"Model {model} not found")

        # Step 3: delete
        await self._request("DELETE", "/api/delete", json={"name": model})

        # Step 4: VERIFY (CRITICAL)
        for _ in range(5):
            if not await self.model_exists(model):
                return
            await asyncio.sleep(0.5)

        raise RuntimeError(f"Model {model} still exists after delete")

    # -------------------------------
    # STREAM APIs (unchanged)
    # -------------------------------
    async def chat_stream(self, model: str, messages: list[dict], options: dict | None = None) -> AsyncIterator[str]:
        payload = {"model": model, "messages": messages, "stream": True, "options": options or {}}

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if data.get("message"):
                            yield data["message"].get("content", "")

    async def pull_model(self, model: str) -> AsyncIterator[dict]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/pull", json={"name": model}) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("data:"):
                        line = line[5:].strip()

                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = await response.aread()
                    if body:
                        try:
                            yield json.loads(body)
                        except json.JSONDecodeError:
                            pass
