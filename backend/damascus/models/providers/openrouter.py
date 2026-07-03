"""
OpenRouter Provider Adapter
============================
Implements the ModelProvider interface for OpenRouter.
OpenRouter is a unified interface to many models, including free options.
"""

from __future__ import annotations

import structlog
import httpx

from damascus.config import settings
from damascus.models.interface import ModelProvider, ModelRequest, ModelResponse

log = structlog.get_logger(__name__)


class OpenRouterProvider(ModelProvider):
    """
    OpenRouter provider adapter.
    """

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _get_model(self, request: ModelRequest) -> str:
        # Default model is specified in configuration (e.g. gpt-4o-mini, or a free llama model)
        return request.model or settings.models.openrouter.default_model

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Send a generation request to OpenRouter."""
        model = self._get_model(request)
        api_key = settings.models.openrouter.api_key

        messages = list(request.messages)
        if request.system_prompt and not any(m.get("role") == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/damascus-org/damascus",
            "X-Title": "Damascus Operating System",
            "Content-Type": "application/json",
        }

        log.debug("Calling OpenRouter", model=model, message_count=len(messages))

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        content = ""
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        usage = data.get("usage", {})

        return ModelResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            finish_reason=choices[0].get("finish_reason", "stop") if choices else "stop",
        )

    async def is_available(self) -> bool:
        """Check if OpenRouter is enabled and key is configured."""
        return settings.models.openrouter.enabled and bool(settings.models.openrouter.api_key)

    async def list_models(self) -> list[str]:
        """Return popular/free models on OpenRouter."""
        if not await self.is_available():
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://openrouter.ai/api/v1/models")
                resp.raise_for_status()
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception as exc:
            log.warning("Failed to fetch OpenRouter models", error=str(exc))
            # Return some common default models
            return [
                "meta-llama/llama-3-8b-instruct:free",
                "google/gemma-2-9b-it:free",
                "mistralai/mistral-7b-instruct:free",
                "openai/gpt-4o-mini",
            ]
