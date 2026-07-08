"""
Model Router — Capability-Aware Provider Selection
=====================================================
Routes model requests to the best available provider based on:
  - Requested model name (explicit routing)
  - Capability requirements (what the model must support)
  - Routing policy (cost, latency, quality, local-first)
  - Provider availability and health
  - Cost constraints

V1 (Phase 1): Simple priority-based routing.
V2 (Phase 2): Capability-aware, policy-driven, cost-constrained routing
              with scoring, fallback, and observability.

Phase 3 will add benchmark-driven quality routing (evidence from Evolution Engine).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from damascus.models.interface import ModelProvider, ModelRequest

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Routing Policy
# ---------------------------------------------------------------------------


class RoutingPolicy(str, Enum):
    """How the router prioritizes candidates."""

    LOCAL_FIRST = "LOCAL_FIRST"
    LOWEST_COST = "LOWEST_COST"
    LOWEST_LATENCY = "LOWEST_LATENCY"
    HIGHEST_QUALITY = "HIGHEST_QUALITY"
    BALANCED = "BALANCED"
    PINNED = "PINNED"


# ---------------------------------------------------------------------------
# Routing Decision Record
# ---------------------------------------------------------------------------


@dataclass
class RoutingDecision:
    """Observable record of why a particular provider was selected."""

    selected_provider: str
    selected_model: str
    policy: RoutingPolicy
    candidates_considered: int
    candidates_eligible: int
    selection_reason: str
    fallback_used: bool = False
    routing_latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ModelRouter:
    """
    Routes generation requests to the best provider using capability-aware
    scoring and policy-driven selection.

    Scoring weights by policy:
      LOCAL_FIRST:     locality 0.6, quality 0.2, latency 0.1, cost 0.1
      LOWEST_COST:     cost 0.6, quality 0.2, locality 0.1, latency 0.1
      LOWEST_LATENCY:  latency 0.6, quality 0.2, locality 0.1, cost 0.1
      HIGHEST_QUALITY: quality 0.6, latency 0.2, cost 0.1, locality 0.1
      BALANCED:        quality 0.3, latency 0.25, cost 0.25, locality 0.2
      PINNED:          direct routing to specified provider (no scoring)
    """

    # Policy → (quality_weight, latency_weight, cost_weight, locality_weight)
    POLICY_WEIGHTS: dict[RoutingPolicy, tuple[float, float, float, float]] = {
        RoutingPolicy.LOCAL_FIRST: (0.2, 0.1, 0.1, 0.6),
        RoutingPolicy.LOWEST_COST: (0.2, 0.1, 0.6, 0.1),
        RoutingPolicy.LOWEST_LATENCY: (0.2, 0.6, 0.1, 0.1),
        RoutingPolicy.HIGHEST_QUALITY: (0.6, 0.2, 0.1, 0.1),
        RoutingPolicy.BALANCED: (0.3, 0.25, 0.25, 0.2),
        RoutingPolicy.PINNED: (0.0, 0.0, 0.0, 0.0),  # not used
    }

    def __init__(
        self,
        providers: list[ModelProvider],
        default_policy: RoutingPolicy = RoutingPolicy.BALANCED,
    ) -> None:
        self._providers = providers
        self._by_name: dict[str, ModelProvider] = {p.provider_name: p for p in providers}
        self._default_policy = default_policy
        self._recent_decisions: list[RoutingDecision] = []

    def _infer_provider_name(self, model: str) -> str | None:
        """
        Infer provider from model name prefix.
        E.g., 'ollama/llama3.1' → 'ollama'
             'openai/gpt-4o'   → 'openai'
             'llama3.1'        → None (use policy routing)
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

    def _score_provider(
        self,
        provider: ModelProvider,
        policy: RoutingPolicy,
    ) -> float:
        """
        Score a provider based on its capabilities and the routing policy.
        Returns 0.0 - 1.0 (higher is better).
        """
        caps = provider.get_capabilities()
        w_quality, w_latency, w_cost, w_locality = self.POLICY_WEIGHTS[policy]

        # Quality score (from QualityClass enum)
        from damascus.models.interface import LatencyClass, QualityClass

        quality_map = {QualityClass.BASIC: 0.3, QualityClass.GOOD: 0.6, QualityClass.EXCELLENT: 1.0}
        quality_score = quality_map.get(caps.quality_class, 0.5)

        # Latency score (inverse — FAST is better)
        latency_map = {LatencyClass.FAST: 1.0, LatencyClass.MEDIUM: 0.6, LatencyClass.SLOW: 0.3}
        latency_score = latency_map.get(caps.latency_class, 0.5)

        # Cost score (local = free = 1.0, cloud = 0.5)
        cost_score = 1.0 if caps.is_local else 0.5

        # Locality score
        locality_score = 1.0 if caps.is_local else 0.0

        return (
            w_quality * quality_score
            + w_latency * latency_score
            + w_cost * cost_score
            + w_locality * locality_score
        )

    def _check_capability_match(
        self, provider: ModelProvider, request: ModelRequest
    ) -> bool:
        """
        Check if a provider satisfies the request's capability requirements.
        Returns True if all required capabilities are satisfied.
        """
        if not request.required_capabilities:
            return True

        caps = provider.get_capabilities()
        provider_caps = set(caps.capabilities)
        required = set(request.required_capabilities)

        return required.issubset(provider_caps)

    def _check_cost_constraint(
        self, provider: ModelProvider, request: ModelRequest
    ) -> bool:
        """Check if the provider's cost estimate is within budget."""
        if request.max_cost_usd is None:
            return True

        estimate = provider.estimate_cost(request)
        return estimate.is_free or estimate.total_cost_usd <= request.max_cost_usd

    def _build_clean_request(
        self, original: ModelRequest, clean_model: str
    ) -> ModelRequest:
        """Create a copy of the request with a cleaned model name."""
        return ModelRequest(
            prompt=original.prompt,
            system_prompt=original.system_prompt,
            model=clean_model,
            temperature=original.temperature,
            max_tokens=original.max_tokens,
            messages=original.messages,
            options=original.options,
            required_capabilities=original.required_capabilities,
            prefer_local=original.prefer_local,
            max_cost_usd=original.max_cost_usd,
        )

    async def select_provider(
        self,
        request: ModelRequest,
        policy: RoutingPolicy | None = None,
    ) -> tuple[ModelProvider, ModelRequest]:
        """
        Select the best provider for this request.
        Returns (provider, modified_request) where model name is cleaned.
        """
        start = time.monotonic()
        active_policy = policy or self._default_policy

        # ------ Explicit provider routing (PINNED / prefix) ------
        if request.model:
            provider_name = self._infer_provider_name(request.model)
            if provider_name and provider_name in self._by_name:
                provider = self._by_name[provider_name]
                if await provider.is_available():
                    clean_model = self.strip_provider_prefix(request.model)
                    decision = RoutingDecision(
                        selected_provider=provider_name,
                        selected_model=clean_model,
                        policy=RoutingPolicy.PINNED,
                        candidates_considered=1,
                        candidates_eligible=1,
                        selection_reason="Explicit provider prefix in model name",
                        routing_latency_ms=(time.monotonic() - start) * 1000,
                    )
                    self._record_decision(decision)
                    return provider, self._build_clean_request(request, clean_model)
                log.warning(
                    "Requested provider not available, falling back",
                    provider=provider_name,
                )

        # ------ Policy-based scoring ------

        # Override policy if request prefers local
        if request.prefer_local:
            active_policy = RoutingPolicy.LOCAL_FIRST

        # Score and filter candidates
        candidates: list[tuple[float, ModelProvider]] = []
        for provider in self._providers:
            if not await provider.is_available():
                continue
            if not self._check_capability_match(provider, request):
                continue
            if not self._check_cost_constraint(provider, request):
                continue
            score = self._score_provider(provider, active_policy)
            candidates.append((score, provider))

        if not candidates:
            from damascus.shared.errors import NoEligibleModelError

            raise NoEligibleModelError()

        # Sort by score descending, select best
        candidates.sort(key=lambda c: c[0], reverse=True)
        best_score, best_provider = candidates[0]

        decision = RoutingDecision(
            selected_provider=best_provider.provider_name,
            selected_model=request.model or "default",
            policy=active_policy,
            candidates_considered=len(self._providers),
            candidates_eligible=len(candidates),
            selection_reason=f"Best score ({best_score:.3f}) under {active_policy.value} policy",
            routing_latency_ms=(time.monotonic() - start) * 1000,
        )
        self._record_decision(decision)

        log.debug(
            "Router selected provider",
            provider=best_provider.provider_name,
            policy=active_policy.value,
            score=round(best_score, 3),
            eligible=len(candidates),
        )
        return best_provider, request

    def _record_decision(self, decision: RoutingDecision) -> None:
        """Store recent routing decisions for observability."""
        self._recent_decisions.append(decision)
        # Keep only last 100 decisions in memory
        if len(self._recent_decisions) > 100:
            self._recent_decisions = self._recent_decisions[-100:]

    async def route_summary(self) -> dict[str, Any]:
        """Return routing summary for observability."""
        providers_info = []
        for idx, p in enumerate(self._providers):
            caps = p.get_capabilities()
            providers_info.append({
                "name": p.provider_name,
                "available": await p.is_available(),
                "priority": idx,
                "quality_class": caps.quality_class.value if hasattr(caps.quality_class, "value") else str(caps.quality_class),
                "latency_class": caps.latency_class.value if hasattr(caps.latency_class, "value") else str(caps.latency_class),
                "is_local": caps.is_local,
            })

        recent = [
            {
                "provider": d.selected_provider,
                "policy": d.policy.value,
                "reason": d.selection_reason,
                "latency_ms": round(d.routing_latency_ms, 2),
            }
            for d in self._recent_decisions[-10:]
        ]

        return {
            "default_policy": self._default_policy.value,
            "providers": providers_info,
            "recent_decisions": recent,
        }
