"""
Unit Tests — Multi-Model Routing (Milestone 2.2)
==================================================
Tests for capability-aware routing, policy-driven scoring,
cost constraints, and fallback behavior.
"""

from __future__ import annotations

import pytest

from damascus.models.interface import (
    CostEstimate,
    LatencyClass,
    ModelCapabilities,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    Modality,
    QualityClass,
)
from damascus.models.router import ModelRouter, RoutingDecision, RoutingPolicy


# ---------------------------------------------------------------------------
# Mock Providers
# ---------------------------------------------------------------------------


class MockLocalProvider(ModelProvider):
    """Simulates a local Ollama-like provider."""

    @property
    def provider_name(self) -> str:
        return "local"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="local response", model="llama3", provider="local")

    async def is_available(self) -> bool:
        return True

    async def list_models(self) -> list[str]:
        return ["llama3", "codellama"]

    def get_capabilities(self, model_name: str | None = None) -> ModelCapabilities:
        return ModelCapabilities(
            modalities=[Modality.TEXT],
            context_window=8192,
            is_local=True,
            latency_class=LatencyClass.MEDIUM,
            quality_class=QualityClass.GOOD,
            capabilities=["reasoning", "coding"],
        )

    def estimate_cost(self, request: ModelRequest) -> CostEstimate:
        return CostEstimate(is_free=True)


class MockCloudProvider(ModelProvider):
    """Simulates a cloud provider like OpenAI."""

    @property
    def provider_name(self) -> str:
        return "cloud"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="cloud response", model="gpt-4o", provider="cloud")

    async def is_available(self) -> bool:
        return True

    async def list_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini"]

    def get_capabilities(self, model_name: str | None = None) -> ModelCapabilities:
        return ModelCapabilities(
            modalities=[Modality.TEXT, Modality.IMAGE],
            context_window=128000,
            supports_tool_calls=True,
            supports_structured_output=True,
            is_local=False,
            latency_class=LatencyClass.FAST,
            quality_class=QualityClass.EXCELLENT,
            capabilities=["reasoning", "coding", "research", "multimodal"],
        )

    def estimate_cost(self, request: ModelRequest) -> CostEstimate:
        return CostEstimate(
            input_cost_usd=0.005,
            output_cost_usd=0.015,
            total_cost_usd=0.020,
            is_free=False,
        )


class MockUnavailableProvider(ModelProvider):
    @property
    def provider_name(self) -> str:
        return "unavailable"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError("Not available")

    async def is_available(self) -> bool:
        return False

    async def list_models(self) -> list[str]:
        return []


class MockExpensiveProvider(ModelProvider):
    """Provider with high cost."""

    @property
    def provider_name(self) -> str:
        return "expensive"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="expensive response", model="exp-1", provider="expensive")

    async def is_available(self) -> bool:
        return True

    async def list_models(self) -> list[str]:
        return ["exp-1"]

    def get_capabilities(self, model_name: str | None = None) -> ModelCapabilities:
        return ModelCapabilities(
            is_local=False,
            latency_class=LatencyClass.SLOW,
            quality_class=QualityClass.EXCELLENT,
            capabilities=["reasoning"],
        )

    def estimate_cost(self, request: ModelRequest) -> CostEstimate:
        return CostEstimate(total_cost_usd=1.50, is_free=False)


# ---------------------------------------------------------------------------
# Interface Tests
# ---------------------------------------------------------------------------


class TestModelCapabilities:
    def test_defaults(self) -> None:
        caps = ModelCapabilities()
        assert caps.modalities == [Modality.TEXT]
        assert caps.context_window == 4096
        assert caps.is_local is False
        assert caps.latency_class == LatencyClass.MEDIUM
        assert caps.quality_class == QualityClass.GOOD

    def test_modality_enum(self) -> None:
        assert Modality.TEXT == "TEXT"
        assert Modality.MULTIMODAL == "MULTIMODAL"


class TestCostEstimate:
    def test_free_cost(self) -> None:
        est = CostEstimate(is_free=True)
        assert est.total_cost_usd == 0.0


class TestModelRequest:
    def test_routing_hints(self) -> None:
        req = ModelRequest(
            prompt="test",
            required_capabilities=["coding"],
            prefer_local=True,
            max_cost_usd=0.01,
        )
        assert req.required_capabilities == ["coding"]
        assert req.prefer_local is True
        assert req.max_cost_usd == 0.01


# ---------------------------------------------------------------------------
# Router Tests
# ---------------------------------------------------------------------------


class TestModelRouter:
    @pytest.mark.asyncio
    async def test_explicit_provider_routing(self) -> None:
        """Model name with provider prefix routes to that provider."""
        router = ModelRouter([MockLocalProvider(), MockCloudProvider()])
        req = ModelRequest(prompt="test", model="local/llama3")

        provider, clean_req = await router.select_provider(req)
        assert provider.provider_name == "local"
        assert clean_req.model == "llama3"

    @pytest.mark.asyncio
    async def test_explicit_cloud_routing(self) -> None:
        router = ModelRouter([MockLocalProvider(), MockCloudProvider()])
        req = ModelRequest(prompt="test", model="cloud/gpt-4o")

        provider, clean_req = await router.select_provider(req)
        assert provider.provider_name == "cloud"
        assert clean_req.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_local_first_policy(self) -> None:
        """LOCAL_FIRST policy should prefer the local provider."""
        router = ModelRouter(
            [MockCloudProvider(), MockLocalProvider()],
            default_policy=RoutingPolicy.LOCAL_FIRST,
        )
        req = ModelRequest(prompt="test")

        provider, _ = await router.select_provider(req)
        assert provider.provider_name == "local"

    @pytest.mark.asyncio
    async def test_highest_quality_policy(self) -> None:
        """HIGHEST_QUALITY should prefer the cloud provider (EXCELLENT quality)."""
        router = ModelRouter(
            [MockLocalProvider(), MockCloudProvider()],
            default_policy=RoutingPolicy.HIGHEST_QUALITY,
        )
        req = ModelRequest(prompt="test")

        provider, _ = await router.select_provider(req)
        assert provider.provider_name == "cloud"

    @pytest.mark.asyncio
    async def test_skip_unavailable_providers(self) -> None:
        """Unavailable providers should be skipped."""
        router = ModelRouter([MockUnavailableProvider(), MockLocalProvider()])
        req = ModelRequest(prompt="test")

        provider, _ = await router.select_provider(req)
        assert provider.provider_name == "local"

    @pytest.mark.asyncio
    async def test_no_eligible_model_error(self) -> None:
        """Should raise NoEligibleModelError when no providers are available."""
        router = ModelRouter([MockUnavailableProvider()])
        req = ModelRequest(prompt="test")

        from damascus.shared.errors import NoEligibleModelError

        with pytest.raises(NoEligibleModelError):
            await router.select_provider(req)

    @pytest.mark.asyncio
    async def test_cost_constraint_filters_expensive(self) -> None:
        """Cost constraint should filter out providers exceeding budget."""
        router = ModelRouter(
            [MockExpensiveProvider(), MockLocalProvider()],
            default_policy=RoutingPolicy.HIGHEST_QUALITY,
        )
        req = ModelRequest(prompt="test", max_cost_usd=0.01)

        provider, _ = await router.select_provider(req)
        # Expensive provider ($1.50) should be filtered; local (free) should win
        assert provider.provider_name == "local"

    @pytest.mark.asyncio
    async def test_prefer_local_overrides_policy(self) -> None:
        """prefer_local=True should override the default policy to LOCAL_FIRST."""
        router = ModelRouter(
            [MockCloudProvider(), MockLocalProvider()],
            default_policy=RoutingPolicy.HIGHEST_QUALITY,
        )
        req = ModelRequest(prompt="test", prefer_local=True)

        provider, _ = await router.select_provider(req)
        assert provider.provider_name == "local"

    @pytest.mark.asyncio
    async def test_capability_filtering(self) -> None:
        """Only providers with required capabilities should be eligible."""
        router = ModelRouter([MockLocalProvider(), MockCloudProvider()])
        req = ModelRequest(
            prompt="test",
            required_capabilities=["multimodal"],
        )

        provider, _ = await router.select_provider(req)
        # Only cloud has "multimodal" capability
        assert provider.provider_name == "cloud"

    @pytest.mark.asyncio
    async def test_route_summary(self) -> None:
        router = ModelRouter([MockLocalProvider(), MockCloudProvider()])
        req = ModelRequest(prompt="test")
        await router.select_provider(req)

        summary = await router.route_summary()
        assert "providers" in summary
        assert "recent_decisions" in summary
        assert len(summary["providers"]) == 2
        assert len(summary["recent_decisions"]) >= 1

    @pytest.mark.asyncio
    async def test_provider_prefix_stripping(self) -> None:
        router = ModelRouter([MockLocalProvider()])
        assert router.strip_provider_prefix("local/llama3") == "llama3"
        assert router.strip_provider_prefix("unknown/model") == "unknown/model"
        assert router.strip_provider_prefix("llama3") == "llama3"


class TestRoutingPolicy:
    def test_all_policies_exist(self) -> None:
        expected = {
            "LOCAL_FIRST", "LOWEST_COST", "LOWEST_LATENCY",
            "HIGHEST_QUALITY", "BALANCED", "PINNED",
        }
        actual = {p.value for p in RoutingPolicy}
        assert actual == expected
