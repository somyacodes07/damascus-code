"""
Model Router — Intelligent provider selection
===============================================
Routes model requests to the best available provider based on:
  - Requested model name
  - Provider availability
  - Capability requirements
  - Cost preferences

V1: Priority-based routing (Ollama first → OpenAI → Anthropic → Gemini → OpenRouter).
Phase 2: Latency-aware, cost-aware, quality-aware routing with benchmarking feedback.
"""

from __future__ import annotations

from typing import Any

import structlog

from damascus.models.interface import ModelProvider, ModelRequest

log = structlog.get_logger(__name__)


class ModelRouter:
    """
    Routes generation requests to the correct provider.

    V1 routing rules:
    1. If model name contains a provider prefix (e.g., 'ollama/', 'openai/'),
       route to that specific provider.
    2. Otherwise, route to the first available provider by priority.
    3. Priority order: Ollama > OpenAI > Anthropic > Gemini > OpenRouter.

    Phase 2 will replace this with benchmark-driven routing.
    """

    def __init__(self, providers: list[ModelProvider]) -> None:
        self._providers = providers
        # Index by provider name for fast lookup
        self._by_name: dict[str, ModelProvider] = {p.provider_name: p for p in providers}

    def _infer_provider_name(self, model: str) -> str | None:
        """
        Infer provider from model name prefix.
        E.g., 'ollama/llama3.1' → 'ollama'
             'openai/gpt-4o'   → 'openai'
             'llama3.1'        → None (use priority routing)
        """
        if "/" in model:
            prefix = model.split("/")[0].lower()
            if prefix in self._by_name:
                return prefix
        return None

    def strip_provider_prefix(self, model: str) -> str:
        """Strip provider prefix from model name for the provider adapter."""
        if "/" in model:
            parts = model.split("/", 1)
            if parts[0].lower() in self._by_name:
                return parts[1]
        return model

    async def select_provider(self, request: ModelRequest) -> tuple[ModelProvider, ModelRequest]:
        """
        Select the best provider for this request.
        Returns (provider, modified_request) where model name is cleaned.
        """
        # Try explicit provider prefix
        if request.model:
            provider_name = self._infer_provider_name(request.model)
            if provider_name and provider_name in self._by_name:
                provider = self._by_name[provider_name]
                if await provider.is_available():
                    clean_model = self.strip_provider_prefix(request.model)
                    return provider, ModelRequest(
                        prompt=request.prompt,
                        system_prompt=request.system_prompt,
                        model=clean_model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        messages=request.messages,
                        options=request.options,
                    )
                log.warning(
                    "Requested provider not available, falling back", provider=provider_name
                )

        # Priority-based fallback
        for provider in self._providers:
            if await provider.is_available():
                log.debug("Router selected provider", provider=provider.provider_name)
                return provider, request

        from damascus.shared.errors import NoModelProviderConfiguredError

        raise NoModelProviderConfiguredError()

    async def route_summary(self) -> dict[str, Any]:
        """Return routing summary for observability."""
        return {
            "providers": [
                {
                    "name": p.provider_name,
                    "available": await p.is_available(),
                    "priority": idx,
                }
                for idx, p in enumerate(self._providers)
            ]
        }
