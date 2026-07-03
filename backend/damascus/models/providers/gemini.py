"""
Gemini Provider Adapter
========================
Implements the ModelProvider interface for Google Gemini.
Gemini offers a very generous free tier (up to 15 RPM) for development.

Get a free key: https://aistudio.google.com/
"""

from __future__ import annotations

import httpx
import structlog

from damascus.config import settings
from damascus.models.interface import ModelProvider, ModelRequest, ModelResponse

log = structlog.get_logger(__name__)


class GeminiProvider(ModelProvider):
    """
    Gemini API provider adapter.
    """

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _get_model(self, request: ModelRequest) -> str:
        return request.model or settings.models.gemini.default_model

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Send a generation request to Google Gemini API."""
        model = self._get_model(request)
        api_key = settings.models.gemini.api_key

        # Standard models: gemini-1.5-flash, gemini-1.5-pro, etc.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        # Convert chat messages to Gemini's format: {"contents": [{"role": "user"|"model", "parts": [{"text": "..."}]}]}
        contents = []
        system_instruction = None

        if request.system_prompt:
            system_instruction = {
                "parts": [{"text": request.system_prompt}]
            }

        for msg in request.messages:
            role = "user" if msg.get("role") in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]
            })

        if request.prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": request.prompt}]
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
            }
        }
        if request.max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = request.max_tokens

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        log.debug("Calling Gemini API", model=model, message_count=len(contents))

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        content = ""
        finish_reason = "stop"
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                content = parts[0].get("text", "")
            finish_reason = candidates[0].get("finishReason", "STOP").lower()

        # Gemini free API doesn't return exact token counts in the metadata by default unless requested,
        # so we calculate simple character-based approximations or use usageMetadata if present.
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", 0)

        return ModelResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
        )

    async def is_available(self) -> bool:
        """Check if Gemini is enabled and key is configured."""
        return settings.models.gemini.enabled and bool(settings.models.gemini.api_key)

    async def list_models(self) -> list[str]:
        return ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
