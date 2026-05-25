"""
Model provider registry - manages multiple providers.
"""
import logging
from typing import Optional

from backend.services.model_provider.base import ModelProvider
from backend.services.model_provider.ollama import OllamaModelProvider

logger = logging.getLogger(__name__)


class ModelProviderRegistry:
    """Registry for managing model providers."""

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}
        self._default_provider: str = "ollama"

    def register(self, name: str, provider: ModelProvider) -> None:
        """Register a model provider."""
        self._providers[name] = provider
        logger.info("Registered model provider: %s", name)

    def get(self, name: str | None = None) -> ModelProvider:
        """Get a provider by name, or the default."""
        provider_name = name or self._default_provider
        if provider_name not in self._providers:
            raise ValueError(f"Unknown model provider: {provider_name}")
        return self._providers[provider_name]

    def set_default(self, name: str) -> None:
        """Set the default provider."""
        if name not in self._providers:
            raise ValueError(f"Cannot set default: provider '{name}' not registered")
        self._default_provider = name

    @property
    def available_providers(self) -> list[str]:
        return list(self._providers.keys())


# Module-level singleton with Ollama pre-registered
model_registry = ModelProviderRegistry()
model_registry.register("ollama", OllamaModelProvider())
