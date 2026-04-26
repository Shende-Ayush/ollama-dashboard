from typing import AsyncIterator


class LiteProvider:
    async def list_models(self) -> list[dict]:
        return [{"name": "lite-fallback", "size": 0, "quantization": "n/a"}]

    async def chat_stream(self, model: str, messages: list[dict], options: dict | None = None) -> AsyncIterator[str]:
        _ = (model, messages, options)
        yield "Lite provider is configured as a future-ready extension point."

    async def stop_model(self, model: str) -> None:
        _ = model
