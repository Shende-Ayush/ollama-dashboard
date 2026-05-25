"""
Ollama model provider implementation.
Wraps the existing OllamaClient with the ModelProvider interface.
"""
import logging
from typing import AsyncIterator

from backend.services.model_provider.base import (
    GenerationOptions,
    ModelInfo,
    ModelProvider,
)
from backend.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class OllamaModelProvider(ModelProvider):
    """Ollama implementation of ModelProvider."""

    def __init__(self, base_url: str | None = None) -> None:
        self.client = OllamaClient(base_url=base_url) if base_url else OllamaClient()

    async def list_models(self) -> list[ModelInfo]:
        raw_models = await self.client.list_models()
        return [
            ModelInfo(
                name=m.get("name", ""),
                size_bytes=m.get("size", 0),
                family=m.get("details", {}).get("family", ""),
                quantization=m.get("details", {}).get("quantization_level", ""),
                supports_fim="code" in m.get("name", "").lower() or "deep" in m.get("name", "").lower(),
                context_window=int(m.get("details", {}).get("context_length", 4096)),
            )
            for m in raw_models
        ]

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        opts = {}
        if options:
            opts["temperature"] = options.temperature
            opts["num_ctx"] = options.num_ctx
            if options.stop:
                opts["stop"] = options.stop

        async for token in self.client.chat_stream(
            model=model, messages=messages, options=opts
        ):
            yield token

    async def generate(
        self,
        model: str,
        prompt: str,
        options: GenerationOptions | None = None,
    ) -> str:
        result = ""
        async for token in self.generate_stream(model, prompt, options):
            result += token
        return result

    async def generate_stream(
        self,
        model: str,
        prompt: str,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        messages = [{"role": "user", "content": prompt}]
        async for token in self.chat_stream(model, messages, options):
            yield token

    async def health_check(self) -> bool:
        try:
            await self.client.list_models()
            return True
        except Exception:
            return False
