"""
Model Service — Provider Router
=================================
Routes model generation requests to the correct provider.
In V1, only Ollama is supported. Multi-model routing comes in Phase 2.

Uses ModelRouter for intelligent provider selection based on model name prefix
or priority-based fallback.
"""

from __future__ import annotations

from typing import Any

import structlog

from damascus.models.interface import ModelProvider, ModelRequest, ModelResponse
from damascus.models.providers.ollama import OllamaProvider
from damascus.models.providers.openrouter import OpenRouterProvider
from damascus.models.providers.gemini import GeminiProvider
from damascus.models.router import ModelRouter
from damascus.shared.errors import NoModelProviderConfiguredError

log = structlog.get_logger(__name__)


class ModelService:
    """
    Model service that routes to available providers via ModelRouter.
    Priority: Ollama -> Gemini -> OpenRouter.
    """

    def __init__(self) -> None:
        self._providers: list[ModelProvider] = [
            OllamaProvider(),
            GeminiProvider(),
            OpenRouterProvider(),
        ]
        self._router = ModelRouter(self._providers)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate text using the router to select the best provider."""
        provider, routed_request = await self._router.select_provider(request)
        log.info("Generating text", provider=provider.provider_name, model=routed_request.model or "default")
        return await provider.generate(routed_request)

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

    async def routing_summary(self) -> dict[str, Any]:
        """Return router state for observability."""
        return await self._router.route_summary()


# Module-level singleton
model_service = ModelService()

