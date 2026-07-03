"""
Model Service — Provider Router
=================================
Routes model generation requests to the correct provider.
In V1, only Ollama is supported. Multi-model routing comes in Phase 2.

The service returns the first available enabled provider by default.
"""

from __future__ import annotations

from typing import Any

import structlog

from damascus.models.interface import ModelProvider, ModelRequest, ModelResponse
from damascus.models.providers.ollama import OllamaProvider
from damascus.shared.errors import NoModelProviderConfiguredError

log = structlog.get_logger(__name__)


class ModelService:
    """
    Model service that routes to available providers.
    V1: Simple priority — Ollama first (local, free, private).
    """

    def __init__(self) -> None:
        self._providers: list[ModelProvider] = [
            OllamaProvider(),
            # OpenAI, Anthropic, Gemini, OpenRouter added in Phase 2
        ]

    async def get_default_provider(self) -> ModelProvider:
        """Return the first available provider. Raises if none configured."""
        for provider in self._providers:
            if await provider.is_available():
                return provider
        raise NoModelProviderConfiguredError()

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate text using the appropriate provider."""
        provider = await self.get_default_provider()
        log.info("Generating text", provider=provider.provider_name, model=request.model or "default")
        return await provider.generate(request)

    async def list_available_models(self) -> dict[str, list[str]]:
        """Return available models grouped by provider."""
        result: dict[str, list[str]] = {}
        for provider in self._providers:
            if await provider.is_available():
                result[provider.provider_name] = await provider.list_models()
        return result

    async def health(self) -> dict[str, Any]:
        """Return health status of each provider."""
        status: dict[str, Any] = {}
        for provider in self._providers:
            status[provider.provider_name] = await provider.is_available()
        return status


# Module-level singleton
model_service = ModelService()
