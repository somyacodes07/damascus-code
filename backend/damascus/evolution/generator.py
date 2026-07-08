"""
Variant Generator — Creates Candidate Improvements
=====================================================
Generates variant configurations from a baseline, applying controlled
mutations that could improve performance.

Mutation strategies:
  - Parameter tuning (temperature, max_tokens, model selection)
  - Prompt refinement (system prompt modifications)
  - Tool selection changes (add/remove available tools)
  - Model swapping (try different models for the same task)

Safety: Variants NEVER modify security constraints, permissions,
or safety policies. These are immutable.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.evolution.models import Variant, VariantStatus

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Mutation Types
# ---------------------------------------------------------------------------


@dataclass
class Mutation:
    """A single mutation applied to create a variant."""

    mutation_type: str  # "temperature", "model", "prompt", "tool_add", "tool_remove"
    field_path: str  # dot-separated path to the mutated field
    original_value: Any
    new_value: Any
    rationale: str


@dataclass
class VariantSpec:
    """Specification for a variant before persistence."""

    name: str
    description: str
    hypothesis: str
    change_set: dict[str, Any]
    mutations: list[Mutation]


# ---------------------------------------------------------------------------
# Safety Constraints
# ---------------------------------------------------------------------------

# Fields that can NEVER be mutated by the evolution engine
IMMUTABLE_FIELDS = frozenset({
    "security_policy",
    "permissions",
    "sandbox_config",
    "approval_requirements",
    "audit_config",
    "workspace_id",
    "id",
})


def validate_safety(change_set: dict[str, Any]) -> bool:
    """
    Verify that a change set does not modify immutable safety constraints.
    Returns True if safe, False if violating.
    """
    for key in change_set:
        if key in IMMUTABLE_FIELDS:
            return False
        # Check nested keys
        if isinstance(change_set[key], dict):
            for nested_key in change_set[key]:
                if nested_key in IMMUTABLE_FIELDS:
                    return False
    return True


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class VariantGenerator:
    """
    Generates variant configurations from a baseline.
    Each mutation is small, testable, and reversible.
    """

    def generate_parameter_variants(
        self,
        baseline_config: dict[str, Any],
        baseline_id: str,
    ) -> list[VariantSpec]:
        """
        Generate variants by tuning numeric parameters.
        Produces variants for: temperature, max_iterations, max_tokens.
        """
        variants: list[VariantSpec] = []

        # Temperature variants
        current_temp = baseline_config.get("temperature", 0.7)
        for temp in [0.1, 0.3, 0.5, 0.7, 0.9, 1.2]:
            if abs(temp - current_temp) < 0.05:
                continue
            change_set = {"temperature": temp}
            if not validate_safety(change_set):
                continue
            variants.append(VariantSpec(
                name=f"Temperature {temp}",
                description=f"Change temperature from {current_temp} to {temp}",
                hypothesis=f"Temperature {temp} may {'improve creativity' if temp > current_temp else 'improve consistency'}",
                change_set=change_set,
                mutations=[Mutation(
                    mutation_type="temperature",
                    field_path="temperature",
                    original_value=current_temp,
                    new_value=temp,
                    rationale=f"Explore effect of temperature={temp}",
                )],
            ))

        # Max iterations variants
        current_iters = baseline_config.get("max_iterations", 10)
        for iters in [5, 10, 15, 20]:
            if iters == current_iters:
                continue
            change_set = {"max_iterations": iters}
            variants.append(VariantSpec(
                name=f"Max iterations {iters}",
                description=f"Change max_iterations from {current_iters} to {iters}",
                hypothesis=f"{'More' if iters > current_iters else 'Fewer'} iterations may {'improve thoroughness' if iters > current_iters else 'reduce cost'}",
                change_set=change_set,
                mutations=[Mutation(
                    mutation_type="max_iterations",
                    field_path="max_iterations",
                    original_value=current_iters,
                    new_value=iters,
                    rationale=f"Explore effect of max_iterations={iters}",
                )],
            ))

        return variants

    def generate_model_variants(
        self,
        baseline_config: dict[str, Any],
        available_models: list[str],
        baseline_id: str,
    ) -> list[VariantSpec]:
        """
        Generate variants by swapping the model.
        Only proposes models that are actually available.
        """
        current_model = baseline_config.get("model_preference", "")
        variants: list[VariantSpec] = []

        for model in available_models:
            if model == current_model:
                continue
            change_set = {"model_preference": model}
            variants.append(VariantSpec(
                name=f"Model: {model}",
                description=f"Swap model from {current_model} to {model}",
                hypothesis=f"Model {model} may perform better for this task",
                change_set=change_set,
                mutations=[Mutation(
                    mutation_type="model",
                    field_path="model_preference",
                    original_value=current_model,
                    new_value=model,
                    rationale=f"Test alternative model: {model}",
                )],
            ))

        return variants

    def generate_prompt_variant(
        self,
        baseline_config: dict[str, Any],
        new_system_prompt: str,
        rationale: str,
        baseline_id: str,
    ) -> VariantSpec:
        """Generate a variant with a modified system prompt."""
        current_prompt = baseline_config.get("system_prompt", "")
        change_set = {"system_prompt": new_system_prompt}
        return VariantSpec(
            name="Prompt refinement",
            description="Modified system prompt",
            hypothesis=rationale,
            change_set=change_set,
            mutations=[Mutation(
                mutation_type="prompt",
                field_path="system_prompt",
                original_value=current_prompt,
                new_value=new_system_prompt,
                rationale=rationale,
            )],
        )

    async def persist_variants(
        self,
        session: AsyncSession,
        experiment_id: str,
        baseline_id: str,
        specs: list[VariantSpec],
    ) -> list[Variant]:
        """Save variant specs to the database."""
        persisted: list[Variant] = []

        for spec in specs:
            # Safety check
            if not validate_safety(spec.change_set):
                from damascus.shared.errors import SafetyConstraintViolationError
                raise SafetyConstraintViolationError()

            variant = Variant(
                experiment_id=experiment_id,
                name=spec.name,
                description=spec.description,
                baseline_version_id=baseline_id,
                change_set=spec.change_set,
                hypothesis=spec.hypothesis,
            )
            session.add(variant)
            persisted.append(variant)

        await session.flush()
        log.info(
            "Persisted variants",
            experiment_id=experiment_id,
            count=len(persisted),
        )
        return persisted


# Module-level singleton
variant_generator = VariantGenerator()
