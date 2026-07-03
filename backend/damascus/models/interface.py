"""
Model Provider — Abstract Interface
=====================================
All model provider adapters must implement this interface.
Damascus never calls provider SDKs directly — only through this abstraction.

This allows the system to swap providers (Ollama → OpenAI) without changes
to the agents, workflows, or any other subsystem.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelRequest:
    """A generation request sent to a model provider."""

    prompt: str
    system_prompt: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    messages: list[dict[str, str]] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """A generation response from a model provider."""

    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelProvider(ABC):
    """
    Abstract interface for all model providers.
    Implement this to add a new provider (OpenAI, Anthropic, Gemini, etc.)
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'ollama', 'openai')."""
        ...

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a text completion from the model."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the provider is reachable and configured."""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """Return a list of available model names for this provider."""
        ...
