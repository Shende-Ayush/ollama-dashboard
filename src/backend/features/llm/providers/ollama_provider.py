from typing import AsyncIterator

from backend.services.ollama_client import OllamaClient


class OllamaProvider:
    def __init__(self) -> None:
        self.client = OllamaClient()

    async def list_models(self) -> list[dict]:
        return await self.client.list_models()

    async def chat_stream(self, model: str, messages: list[dict], options: dict | None = None) -> AsyncIterator[str]:
        async for token in self.client.chat_stream(model=model, messages=messages, options=options):
            yield token

    async def stop_model(self, model: str) -> None:
        await self.client.stop_model(model)
