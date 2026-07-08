"""
Research Service — Business Logic
====================================
Manages research tasks: creation, execution, finding storage, and synthesis.

The research service is an agent-callable capability. Agents in workflows
can spawn research tasks to gather external information needed for
decision-making.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from damascus.research.models import (
    FindingType,
    ResearchFinding,
    ResearchStatus,
    ResearchTask,
)
from damascus.shared.errors import ResearchTaskNotFoundError

log = structlog.get_logger(__name__)


class ResearchService:
    """Manages research task lifecycle and finding aggregation."""

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    async def create_task(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        query: str,
        scope: str = "web",
        max_sources: int = 10,
        output_format: str = "summary",
    ) -> ResearchTask:
        task = ResearchTask(
            workspace_id=workspace_id,
            query=query,
            scope=scope,
            max_sources=max_sources,
            output_format=output_format,
        )
        session.add(task)
        await session.flush()
        log.info("Created research task", task_id=task.id, query=query[:80])
        return task

    async def get_task(
        self, session: AsyncSession, task_id: str
    ) -> ResearchTask:
        result = await session.execute(
            select(ResearchTask)
            .where(ResearchTask.id == task_id)
            .options(selectinload(ResearchTask.findings))
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise ResearchTaskNotFoundError(task_id=task_id)
        return task

    async def list_tasks(
        self,
        session: AsyncSession,
        workspace_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[ResearchTask], int]:
        from sqlalchemy import func

        base = select(ResearchTask).where(ResearchTask.workspace_id == workspace_id)
        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        result = await session.scalars(
            base.order_by(ResearchTask.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.all()), total

    # ------------------------------------------------------------------
    # Task Execution
    # ------------------------------------------------------------------

    async def start_task(
        self, session: AsyncSession, task_id: str
    ) -> ResearchTask:
        """Mark a task as RUNNING."""
        task = await self.get_task(session, task_id)
        task.status = ResearchStatus.RUNNING
        await session.flush()
        return task

    async def complete_task(
        self,
        session: AsyncSession,
        task_id: str,
        result_summary: str,
    ) -> ResearchTask:
        """Mark a task as COMPLETED with summary."""
        task = await self.get_task(session, task_id)
        task.status = ResearchStatus.COMPLETED
        task.result_summary = result_summary
        task.completed_at = datetime.now(UTC)
        await session.flush()
        log.info("Research task completed", task_id=task_id)
        return task

    async def fail_task(
        self, session: AsyncSession, task_id: str, error: str
    ) -> ResearchTask:
        """Mark a task as FAILED."""
        task = await self.get_task(session, task_id)
        task.status = ResearchStatus.FAILED
        task.error_message = error
        task.completed_at = datetime.now(UTC)
        await session.flush()
        return task

    # ------------------------------------------------------------------
    # Finding Management
    # ------------------------------------------------------------------

    async def add_finding(
        self,
        session: AsyncSession,
        *,
        task_id: str,
        finding_type: str = FindingType.FACT,
        content: str,
        relevance_score: float = 0.0,
        source_url: str = "",
        source_title: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ResearchFinding:
        """Add a finding to a research task."""
        finding = ResearchFinding(
            task_id=task_id,
            finding_type=finding_type,
            content=content,
            relevance_score=relevance_score,
            source_url=source_url,
            source_title=source_title,
            finding_metadata=metadata or {},
        )
        session.add(finding)
        await session.flush()
        return finding

    async def get_findings(
        self,
        session: AsyncSession,
        task_id: str,
        min_relevance: float = 0.0,
    ) -> list[ResearchFinding]:
        """Get findings for a task, optionally filtered by relevance."""
        result = await session.scalars(
            select(ResearchFinding)
            .where(
                ResearchFinding.task_id == task_id,
                ResearchFinding.relevance_score >= min_relevance,
            )
            .order_by(ResearchFinding.relevance_score.desc())
        )
        return list(result.all())


# Module-level singleton
research_service = ResearchService()
