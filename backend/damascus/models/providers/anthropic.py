"""
Anthropic Provider Adapter
============================
Implements the ModelProvider interface for Anthropic's Messages API.

Uses httpx for consistency with other Damascus providers (no SDK dependency).
Anthropic has a unique API shape — system prompts are a top-level field,
not a message role.

Get an API key: https://console.anthropic.com/settings/keys
"""

from __future__ import annotations

import httpx
import structlog

from damascus.config import settings
from damascus.models.interface import ModelProvider, ModelRequest, ModelResponse

log = structlog.get_logger(__name__)

_ANTHROPIC_API_BASE = "https://api.anthropic.com/v1"
_ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider(ModelProvider):
    """
    Anthropic provider adapter.
    Calls the Anthropic Messages API via httpx.
    """

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_model(self, request: ModelRequest) -> str:
        return request.model or settings.models.anthropic.default_model

    def _build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": settings.models.anthropic.api_key,
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_API_VERSION,
        }

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Send a generation request to Anthropic Messages API."""
        model = self._get_model(request)

        # Build message list — Anthropic uses "user" and "assistant" roles only.
        # System prompt is a top-level field, NOT a message.
        messages: list[dict[str, str]] = []
        for msg in request.messages:
            role = msg.get("role", "user")
            # Map "system" messages to user messages (system is top-level in Anthropic)
            if role == "system":
                continue
            messages.append({
                "role": role if role in ("user", "assistant") else "user",
                "content": msg.get("content", ""),
            })

        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        # Anthropic requires at least one message
        if not messages:
            messages = [{"role": "user", "content": request.prompt or "Hello"}]

        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }

        # System prompt as top-level field
        system_prompt = request.system_prompt
        if not system_prompt:
            # Check if any message was a system message
            for msg in request.messages:
                if msg.get("role") == "system":
                    system_prompt = msg.get("content", "")
                    break
        if system_prompt:
            payload["system"] = system_prompt

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        # Forward extra options
        if request.options:
            for key in ("top_p", "top_k", "stop_sequences"):
                if key in request.options:
                    payload[key] = request.options[key]

        log.debug("Calling Anthropic", model=model, message_count=len(messages))

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{_ANTHROPIC_API_BASE}/messages",
                headers=self._build_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # Parse response — Anthropic returns content as a list of blocks
        content_blocks = data.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        finish_reason = data.get("stop_reason", "end_turn")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        return ModelResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason=finish_reason,
            metadata={"id": data.get("id", "")},
        )

    async def is_available(self) -> bool:
        """Check if Anthropic is enabled and key is configured."""
        return settings.models.anthropic.enabled and bool(settings.models.anthropic.api_key)

    async def list_models(self) -> list[str]:
        """Return list of available Anthropic models."""
        # Anthropic doesn't have a public model listing endpoint,
        # return known models.
        return [
            "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
        ]
