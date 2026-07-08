"""
Model Service — Provider Router
=================================
Routes model generation requests to the correct provider.

Phase 2 additions:
  - OpenAI and Anthropic provider adapters
  - Dynamic provider loading (only enabled providers are instantiated)
  - Routing policy support
  - Cost tracking accumulation
  - Enhanced observability
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from damascus.config import settings
from damascus.models.interface import ModelProvider, ModelRequest, ModelResponse
from damascus.models.router import ModelRouter, RoutingPolicy

log = structlog.get_logger(__name__)


def _build_providers() -> list[ModelProvider]:
    """
    Build the provider list dynamically based on configuration.
    Only instantiates enabled providers.
    """
    providers: list[ModelProvider] = []

    # Ollama (local-first, always first priority if enabled)
    if settings.models.ollama.enabled:
        from damascus.models.providers.ollama import OllamaProvider

        providers.append(OllamaProvider())

    # Gemini (free tier available)
    if settings.models.gemini.enabled:
        from damascus.models.providers.gemini import GeminiProvider

        providers.append(GeminiProvider())

    # OpenAI
    if settings.models.openai.enabled:
        from damascus.models.providers.openai import OpenAIProvider

        providers.append(OpenAIProvider())

    # Anthropic
    if settings.models.anthropic.enabled:
        from damascus.models.providers.anthropic import AnthropicProvider

        providers.append(AnthropicProvider())

    # OpenRouter (fallback, aggregates many providers)
    if settings.models.openrouter.enabled:
        from damascus.models.providers.openrouter import OpenRouterProvider

        providers.append(OpenRouterProvider())

    return providers


class ModelService:
    """
    Model service that routes to available providers via ModelRouter.
    Dynamically loads only enabled providers.
    """

    def __init__(self) -> None:
        self._providers: list[ModelProvider] = _build_providers()
        self._router = ModelRouter(self._providers)

        # Cost tracking (in-memory for V2; persistent in V3)
        self._total_cost_usd: float = 0.0
        self._total_requests: int = 0

    async def generate(
        self,
        request: ModelRequest,
        policy: RoutingPolicy | None = None,
    ) -> ModelResponse:
        """Generate text using the router to select the best provider."""
        start = time.monotonic()

        provider, routed_request = await self._router.select_provider(request, policy=policy)

        log.info(
            "Generating text",
            provider=provider.provider_name,
            model=routed_request.model or "default",
        )

        response = await provider.generate(routed_request)

        # Attach latency
        response.latency_ms = int((time.monotonic() - start) * 1000)

        # Attach cost estimate
        cost = provider.estimate_cost(routed_request)
        response.estimated_cost_usd = cost.total_cost_usd

        # Track cumulative cost
        self._total_cost_usd += response.estimated_cost_usd
        self._total_requests += 1

        return response

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
        summary = await self._router.route_summary()
        summary["total_requests"] = self._total_requests
        summary["total_cost_usd"] = round(self._total_cost_usd, 6)
        return summary

    async def get_provider_capabilities(self) -> dict[str, Any]:
        """Return capabilities of all loaded providers."""
        result: dict[str, Any] = {}
        for provider in self._providers:
            caps = provider.get_capabilities()
            result[provider.provider_name] = {
                "available": await provider.is_available(),
                "modalities": [m.value for m in caps.modalities],
                "context_window": caps.context_window,
                "is_local": caps.is_local,
                "quality_class": caps.quality_class.value,
                "latency_class": caps.latency_class.value,
                "supports_tool_calls": caps.supports_tool_calls,
                "supports_structured_output": caps.supports_structured_output,
            }
        return result


# Module-level singleton
model_service = ModelService()
