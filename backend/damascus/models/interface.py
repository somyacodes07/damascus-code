"""
Model Provider — Abstract Interface
=====================================
All model provider adapters must implement this interface.
Damascus never calls provider SDKs directly — only through this abstraction.

This allows the system to swap providers (Ollama → OpenAI) without changes
to the agents, workflows, or any other subsystem.

Phase 2 additions:
  - ModelCapabilities — declares what a provider/model can do
  - CostEstimate — pre-execution cost estimation
  - get_capabilities() — optional capability declaration
  - estimate_cost() — optional cost estimation
  - Extended ModelResponse with latency and cost tracking
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Capability Model
# ---------------------------------------------------------------------------


class Modality(str, Enum):
    """What types of input/output a model supports."""

    TEXT = "TEXT"
    IMAGE = "IMAGE"
    CODE = "CODE"
    AUDIO = "AUDIO"
    MULTIMODAL = "MULTIMODAL"


class LatencyClass(str, Enum):
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    SLOW = "SLOW"


class QualityClass(str, Enum):
    BASIC = "BASIC"
    GOOD = "GOOD"
    EXCELLENT = "EXCELLENT"


@dataclass
class ModelCapabilities:
    """
    Declares what a model can do.
    Used by the router to match requests to providers.
    """

    modalities: list[Modality] = field(default_factory=lambda: [Modality.TEXT])
    context_window: int = 4096
    supports_structured_output: bool = False
    supports_tool_calls: bool = False
    supports_streaming: bool = True
    is_local: bool = False
    latency_class: LatencyClass = LatencyClass.MEDIUM
    quality_class: QualityClass = QualityClass.GOOD
    capabilities: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cost Model
# ---------------------------------------------------------------------------


@dataclass
class CostEstimate:
    """Pre-execution cost estimation for a request."""

    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    is_free: bool = False


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------


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

    # Phase 2: routing hints
    required_capabilities: list[str] = field(default_factory=list)
    prefer_local: bool = False
    max_cost_usd: float | None = None


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

    # Phase 2: observability
    latency_ms: int = 0
    estimated_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Provider Interface
# ---------------------------------------------------------------------------


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

    # Phase 2 optional methods with defaults

    def get_capabilities(self, model_name: str | None = None) -> ModelCapabilities:
        """
        Return capability metadata for this provider or a specific model.
        Override in concrete providers for accurate routing.
        """
        return ModelCapabilities()

    def estimate_cost(self, request: ModelRequest) -> CostEstimate:
        """
        Estimate the cost of a request before executing it.
        Override in concrete providers for cost-aware routing.
        """
        return CostEstimate(is_free=True)
