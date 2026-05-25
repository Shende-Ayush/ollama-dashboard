"""
Abstract model provider interface.
Supports: Ollama, OpenAI-compatible APIs, vLLM.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Any


@dataclass
class ModelInfo:
    """Information about an available model."""
    name: str
    size_bytes: int = 0
    family: str = ""
    quantization: str = ""
    supports_fim: bool = False
    context_window: int = 4096


@dataclass 
class ChatMessage:
    """A chat message."""
    role: str  # system, user, assistant
    content: str


@dataclass
class GenerationOptions:
    """Options for text generation."""
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    stop: list[str] = field(default_factory=list)
    num_ctx: int = 4096


class ModelProvider(ABC):
    """Abstract base class for model providers."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """List available models."""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        ...

    @abstractmethod
    async def generate(
        self,
        model: str,
        prompt: str,
        options: GenerationOptions | None = None,
    ) -> str:
        """Generate text (non-streaming)."""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        model: str,
        prompt: str,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream text generation tokens."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        ...
