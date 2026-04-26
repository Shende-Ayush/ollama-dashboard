We need to apply suggested edit to the original code. The suggested edit is a very simplified version with only generate method, but we need to apply it to the original code. That likely means replace the original file content with the new code? However instructions: "Apply the SUGGESTED EDIT to the ORIGINAL CODE. Output the complete modified file." The suggested edit replaces imports and adds new class content. The original code had many methods (list_models, list_running, chat_stream, pull_model, stop_model) and circuit breaker logic. The suggested edit introduces a new __init__ signature (base_url param), sets timeout, and adds generate method. Should we keep original methods? The suggestion seems to replace code, not merge. But typical tasks: incorporate suggested edit modifications into original code, preserving other parts unless overridden. The suggested edit changes imports: removes json, os, typing AsyncIterator, imports only httpx, typing Any, Dict. Also changes class init signature, adds default base_url, adds timeout attribute. Also removes circuit_breaker usage. Probably we should replace the original file with the suggested simplified version; i.e., drop all other methods. But the instruction: "Apply the SUGGESTED EDIT to the ORIGINAL CODE." Usually means edit original code accordingly: modify imports, class __init__, maybe add generate method, but keep existing methods? The suggested edit only includes generate; it does not mention removing other methods. However the suggested edit changes signature of __init__ and adds timeout attribute; we can integrate that while preserving other methods. Circuit breaker logic may be removed? The suggested edit doesn't mention circuit breaker; but applying edit might replace the __init__ entirely, removing environment variable usage, and add timeout attribute. Should we also remove circuit_breaker references? The suggestion doesn't mention them, but applying the edit likely means to adopt the new simpler design, discarding circuit breaker and other methods. The safe approach: replace the whole file content with the suggested version; but the instruction to "preserve all unchanged code exactly as-is" suggests we keep unchanged code, but changed parts are replaced. The edit changes imports, class definition, and adds generate method. The original had many methods; they are not part of suggested edit. Since suggested edit does not include those methods, they would be removed, which is a change. But "preserve all unchanged code exactly as-is" means only changed parts should be updated; other parts remain. However the suggested edit is a completely different class. I think they expect to replace the original with the new simplified version, discarding the previous methods. But then the rest would not be unchanged. The instruction says "Apply the SUGGESTED EDIT to the ORIGINAL CODE." The suggested edit is minimal; we should replace the entire file? Probably. I'll output the new file containing only the suggested code.

from typing import AsyncIterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.services.circuit_breaker import circuit_breaker


class OllamaClient:
    def __init__(self) -> None:
        host = os.getenv("OLLAMA_HOST", "localhost")
        port = os.getenv("OLLAMA_PORT", "11434")
        self.base_url = f"http://{host}:{port}"

    @retry(wait=wait_exponential(min=0.2, max=2), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    async def list_models(self) -> list[dict]:
        if not circuit_breaker.allow():
            raise httpx.HTTPError("Ollama circuit breaker open")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                circuit_breaker.record_success()
                return resp.json().get("models", [])
        except httpx.HTTPError:
            circuit_breaker.record_failure()
            raise

    @retry(wait=wait_exponential(min=0.2, max=2), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.HTTPError))
    async def list_running(self) -> list[dict]:
        if not circuit_breaker.allow():
            raise httpx.HTTPError("Ollama circuit breaker open")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(f"{self.base_url}/api/ps")
                resp.raise_for_status()
                circuit_breaker.record_success()
                return resp.json().get("models", [])
        except httpx.HTTPError:
            circuit_breaker.record_failure()
            raise

    async def chat_stream(self, model: str, messages: list[dict], options: dict | None = None) -> AsyncIterator[str]:
        if not circuit_breaker.allow():
            raise httpx.HTTPError("Ollama circuit breaker open")
        payload = {"model": model, "messages": messages, "stream": True, "options": options or {}}
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    circuit_breaker.record_success()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
        except httpx.HTTPError:
            circuit_breaker.record_failure()
            raise

    async def pull_model(self, model: str) -> AsyncIterator[dict]:
        if not circuit_breaker.allow():
            raise httpx.HTTPError("Ollama circuit breaker open")
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{self.base_url}/api/pull", json={"name": model, "stream": True}) as resp:
                    resp.raise_for_status()
                    circuit_breaker.record_success()
                    async for line in resp.aiter_lines():
                        if line:
                            yield json.loads(line)
        except httpx.HTTPError:
            circuit_breaker.record_failure()
            raise

    async def stop_model(self, model: str) -> None:
        async with httpx.AsyncClient(timeout=20.0) as client:
            await client.post(f"{self.base_url}/api/generate", json={"model": model, "prompt": "", "keep_alive": 0})
