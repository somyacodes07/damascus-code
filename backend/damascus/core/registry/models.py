"""Model Registry — stores provider info, capabilities, context limits, routing metadata."""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


class ModelRegistry:
    """Manages model provider registrations. Backed by PostgreSQL via models/service.py."""

    async def get_available_providers(self) -> list[str]:
        """Return a list of enabled provider names."""
        from damascus.config import settings

        providers = []
        if settings.models.ollama.enabled:
            providers.append("ollama")
        if settings.models.openai.enabled:
            providers.append("openai")
        if settings.models.anthropic.enabled:
            providers.append("anthropic")
        if settings.models.gemini.enabled:
            providers.append("gemini")
        if settings.models.openrouter.enabled:
            providers.append("openrouter")
        return providers


model_registry = ModelRegistry()
