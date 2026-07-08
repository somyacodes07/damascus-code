"""
Opportunity Analyzer — Identifies Evolution Candidates
========================================================
Ingests workflow traces, failure patterns, and performance data to identify
candidate weaknesses that could be improved through evolution.

Detection strategies:
  - Repeated failures on the same step
  - High latency compared to peers
  - Excessive token/cost usage
  - Low quality scores
  - Recurring user corrections

Output: Ranked list of EvolutionOpportunity records with evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.agents.models import AgentPerformance
from damascus.evolution.models import EvolutionOpportunity, OpportunityType

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Analysis Result
# ---------------------------------------------------------------------------


@dataclass
class OpportunityCandidate:
    """An identified improvement candidate before persistence."""

    target_id: str
    target_type: str
    opportunity_type: OpportunityType
    description: str
    evidence: dict[str, Any]
    priority_score: float  # 0.0 - 1.0 (higher = more urgent)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class OpportunityAnalyzer:
    """
    Analyzes workflow traces and performance data to identify
    evolution opportunities.
    """

    # Thresholds for detection
    FAILURE_RATE_THRESHOLD = 0.3  # >30% failure rate
    LOW_QUALITY_THRESHOLD = 0.5  # <0.5 average quality
    HIGH_LATENCY_MULTIPLIER = 2.0  # >2x average latency
    MIN_SAMPLES = 3  # Minimum executions before analysis

    async def analyze_agent_performance(
        self,
        session: AsyncSession,
        workspace_id: str,
    ) -> list[OpportunityCandidate]:
        """
        Analyze all agent performance records in a workspace
        and identify improvement opportunities.
        """
        candidates: list[OpportunityCandidate] = []

        # Get all performance records grouped by agent
        result = await session.execute(
            select(AgentPerformance)
            .join(AgentPerformance.agent)
            .where(AgentPerformance.agent.has(workspace_id=workspace_id))
            .order_by(AgentPerformance.recorded_at.desc())
            .limit(500)
        )
        records = list(result.scalars().all())

        # Group by agent
        by_agent: dict[str, list[AgentPerformance]] = {}
        for r in records:
            by_agent.setdefault(r.agent_profile_id, []).append(r)

        for agent_id, agent_records in by_agent.items():
            if len(agent_records) < self.MIN_SAMPLES:
                continue

            candidates.extend(self._analyze_single_agent(agent_id, agent_records))

        # Sort by priority (highest first)
        candidates.sort(key=lambda c: c.priority_score, reverse=True)

        log.info(
            "Opportunity analysis complete",
            workspace_id=workspace_id,
            agents_analyzed=len(by_agent),
            opportunities_found=len(candidates),
        )
        return candidates

    def _analyze_single_agent(
        self, agent_id: str, records: list[AgentPerformance]
    ) -> list[OpportunityCandidate]:
        """Analyze a single agent's performance for improvement opportunities."""
        candidates: list[OpportunityCandidate] = []
        total = len(records)

        # --- Failure rate analysis ---
        failures = sum(1 for r in records if not r.success)
        failure_rate = failures / total
        if failure_rate > self.FAILURE_RATE_THRESHOLD:
            candidates.append(OpportunityCandidate(
                target_id=agent_id,
                target_type="AGENT",
                opportunity_type=OpportunityType.REPEATED_FAILURE,
                description=f"Agent has {failure_rate:.0%} failure rate over {total} executions",
                evidence={
                    "failure_rate": round(failure_rate, 4),
                    "total_executions": total,
                    "failure_count": failures,
                    "recent_failures": [
                        {"execution_id": r.execution_id, "task_type": r.task_type}
                        for r in records[:5] if not r.success
                    ],
                },
                priority_score=min(1.0, failure_rate * 1.5),
            ))

        # --- Quality score analysis ---
        quality_scores = [r.quality_score for r in records if r.quality_score > 0]
        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)
            if avg_quality < self.LOW_QUALITY_THRESHOLD:
                candidates.append(OpportunityCandidate(
                    target_id=agent_id,
                    target_type="AGENT",
                    opportunity_type=OpportunityType.LOW_QUALITY,
                    description=f"Agent average quality score is {avg_quality:.2f} (threshold: {self.LOW_QUALITY_THRESHOLD})",
                    evidence={
                        "avg_quality_score": round(avg_quality, 4),
                        "threshold": self.LOW_QUALITY_THRESHOLD,
                        "sample_size": len(quality_scores),
                    },
                    priority_score=min(1.0, (self.LOW_QUALITY_THRESHOLD - avg_quality) * 2),
                ))

        # --- Latency analysis ---
        latencies = [r.latency_ms for r in records if r.latency_ms > 0]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            if max_latency > avg_latency * self.HIGH_LATENCY_MULTIPLIER and avg_latency > 1000:
                candidates.append(OpportunityCandidate(
                    target_id=agent_id,
                    target_type="AGENT",
                    opportunity_type=OpportunityType.HIGH_LATENCY,
                    description=f"Agent has latency spikes up to {max_latency}ms (avg: {avg_latency:.0f}ms)",
                    evidence={
                        "avg_latency_ms": round(avg_latency, 1),
                        "max_latency_ms": max_latency,
                        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
                        "sample_size": len(latencies),
                    },
                    priority_score=0.4,
                ))

        # --- Cost analysis ---
        token_usages = [r.token_usage for r in records if r.token_usage > 0]
        if token_usages:
            avg_tokens = sum(token_usages) / len(token_usages)
            if avg_tokens > 10000:  # >10k tokens average per invocation
                candidates.append(OpportunityCandidate(
                    target_id=agent_id,
                    target_type="AGENT",
                    opportunity_type=OpportunityType.EXCESSIVE_COST,
                    description=f"Agent averages {avg_tokens:.0f} tokens per invocation",
                    evidence={
                        "avg_token_usage": round(avg_tokens, 0),
                        "total_tokens": sum(token_usages),
                        "sample_size": len(token_usages),
                    },
                    priority_score=0.3,
                ))

        return candidates

    async def persist_opportunities(
        self,
        session: AsyncSession,
        workspace_id: str,
        candidates: list[OpportunityCandidate],
    ) -> list[EvolutionOpportunity]:
        """Save identified opportunities to the database."""
        persisted: list[EvolutionOpportunity] = []
        for c in candidates:
            opp = EvolutionOpportunity(
                workspace_id=workspace_id,
                target_id=c.target_id,
                target_type=c.target_type,
                opportunity_type=c.opportunity_type.value,
                description=c.description,
                evidence=c.evidence,
                priority_score=c.priority_score,
            )
            session.add(opp)
            persisted.append(opp)
        await session.flush()
        return persisted


# Module-level singleton
opportunity_analyzer = OpportunityAnalyzer()
