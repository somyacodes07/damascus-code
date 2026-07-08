"""
OpenAI Provider Adapter
========================
Implements the ModelProvider interface for OpenAI's Chat Completions API.

Uses httpx for consistency with other Damascus providers (no SDK dependency).

Get an API key: https://platform.openai.com/api-keys
"""

from __future__ import annotations

import httpx
import structlog

from damascus.config import settings
from damascus.models.interface import ModelProvider, ModelRequest, ModelResponse

log = structlog.get_logger(__name__)

_OPENAI_API_BASE = "https://api.openai.com/v1"


class OpenAIProvider(ModelProvider):
    """
    OpenAI provider adapter.
    Calls the OpenAI Chat Completions API via httpx.
    """

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_model(self, request: ModelRequest) -> str:
        return request.model or settings.models.openai.default_model

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.models.openai.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Send a generation request to OpenAI Chat Completions API."""
        model = self._get_model(request)

        # Build message list
        messages: list[dict[str, str]] = list(request.messages)
        if request.system_prompt and not any(m.get("role") == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Forward any extra options
        if request.options:
            for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
                if key in request.options:
                    payload[key] = request.options[key]

        log.debug("Calling OpenAI", model=model, message_count=len(messages))

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{_OPENAI_API_BASE}/chat/completions",
                headers=self._build_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        finish_reason = choice.get("finish_reason", "stop")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        return ModelResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            metadata={"id": data.get("id", "")},
        )

    async def is_available(self) -> bool:
        """Check if OpenAI is enabled and key is configured."""
        return settings.models.openai.enabled and bool(settings.models.openai.api_key)

    async def list_models(self) -> list[str]:
        """Return list of available OpenAI models."""
        if not await self.is_available():
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_OPENAI_API_BASE}/models",
                    headers=self._build_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                # Filter to chat-capable models
                return sorted(
                    m["id"]
                    for m in data.get("data", [])
                    if "gpt" in m.get("id", "")
                )
        except Exception as exc:
            log.warning("Failed to list OpenAI models", error=str(exc))
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
