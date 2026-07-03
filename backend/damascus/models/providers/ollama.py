"""
Ollama Provider Adapter
========================
Implements the ModelProvider interface for Ollama (local models).
Ollama is the recommended provider for development — free, private, local.

Requires Ollama to be running: https://ollama.com
Pull a model first: ollama pull llama3.1
"""

from __future__ import annotations

import structlog
import httpx

from damascus.config import settings
from damascus.models.interface import ModelProvider, ModelRequest, ModelResponse

log = structlog.get_logger(__name__)


class OllamaProvider(ModelProvider):
    """
    Ollama provider adapter.
    Calls the Ollama REST API to generate text completions using local models.
    """

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _get_model(self, request: ModelRequest) -> str:
        return request.model or settings.models.ollama.default_model

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Send a generation request to Ollama."""
        model = self._get_model(request)
        endpoint = settings.models.ollama.endpoint

        # Build message list (chat format)
        messages = list(request.messages)
        if request.system_prompt and not any(m.get("role") == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                **request.options,
            },
        }

        log.debug("Calling Ollama", model=model, message_count=len(messages))

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{endpoint}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        usage = data.get("prompt_eval_count", 0), data.get("eval_count", 0)

        return ModelResponse(
            content=message.get("content", ""),
            model=model,
            provider=self.provider_name,
            prompt_tokens=usage[0],
            completion_tokens=usage[1],
            total_tokens=usage[0] + usage[1],
            finish_reason=data.get("done_reason", "stop"),
        )

    async def is_available(self) -> bool:
        """Check if Ollama is running and reachable."""
        if not settings.models.ollama.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.models.ollama.endpoint}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Return list of locally available Ollama models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.models.ollama.endpoint}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            log.warning("Failed to list Ollama models", error=str(exc))
            return []
