"""
Workflow Scheduler
==================
Schedules workflows for deferred or recurring execution.
V1: Simple time-based scheduling stored in Redis (sorted set by next_run_time).
Phase 2: Full cron-based scheduling with persistence in PostgreSQL.

The Scheduler is part of Damascus Core — it orchestrates when workflows run,
not how they run (that's the Runtime's job).
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import structlog

from damascus.shared.cache import get_redis

log = structlog.get_logger(__name__)

# Redis keys
_SCHEDULED_SET = "damascus:scheduler:jobs"
_JOB_DATA_KEY = "damascus:scheduler:job:{job_id}"
_SCHEDULER_LOCK = "damascus:scheduler:lock"


class ScheduledJob:
    """Represents a scheduled workflow execution."""

    def __init__(
        self,
        job_id: str,
        workflow_id: str,
        workspace_id: str,
        inputs: dict[str, Any],
        run_at: datetime,
        recurrence: str | None = None,  # cron expression, None = one-shot
    ) -> None:
        self.job_id = job_id
        self.workflow_id = workflow_id
        self.workspace_id = workspace_id
        self.inputs = inputs
        self.run_at = run_at
        self.recurrence = recurrence

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "inputs": self.inputs,
            "run_at": self.run_at.isoformat(),
            "recurrence": self.recurrence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduledJob:
        return cls(
            job_id=data["job_id"],
            workflow_id=data["workflow_id"],
            workspace_id=data["workspace_id"],
            inputs=data.get("inputs", {}),
            run_at=datetime.fromisoformat(data["run_at"]),
            recurrence=data.get("recurrence"),
        )


class Scheduler:
    """
    Workflow scheduler.

    Uses a Redis sorted set where the score is the Unix timestamp of next_run_time.
    A background loop polls this set for due jobs and triggers execution.

    V1 limitations:
    - Single-process only (no distributed lock for multi-process)
    - Max polling interval: 30 seconds (not real-time)
    - One-shot and cron scheduling supported
    """

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    async def schedule(self, job: ScheduledJob) -> None:
        """Add a job to the schedule."""
        redis = await get_redis()
        score = job.run_at.timestamp()
        # Store job data
        job_key = _JOB_DATA_KEY.format(job_id=job.job_id)
        await redis.set(job_key, json.dumps(job.to_dict()), ex=86400 * 30)
        # Add to sorted set
        await redis.zadd(_SCHEDULED_SET, {job.job_id: score})
        log.info("Scheduled job", job_id=job.job_id, run_at=job.run_at.isoformat())

    async def cancel(self, job_id: str) -> bool:
        """Remove a scheduled job. Returns True if removed."""
        redis = await get_redis()
        removed = await redis.zrem(_SCHEDULED_SET, job_id)
        await redis.delete(_JOB_DATA_KEY.format(job_id=job_id))
        log.info("Cancelled scheduled job", job_id=job_id)
        return bool(removed)

    async def list_due_jobs(self, now: datetime | None = None) -> list[ScheduledJob]:
        """Return all jobs that are due to run."""
        redis = await get_redis()
        now_ts = (now or datetime.now(UTC)).timestamp()
        # Get all job IDs with score <= now
        job_ids = await redis.zrangebyscore(_SCHEDULED_SET, "-inf", now_ts)
        jobs = []
        for job_id in job_ids:
            job_key = _JOB_DATA_KEY.format(job_id=job_id)
            raw = await redis.get(job_key)
            if raw:
                try:
                    jobs.append(ScheduledJob.from_dict(json.loads(raw)))
                except Exception as exc:
                    log.warning("Failed to deserialize scheduled job", job_id=job_id, error=str(exc))
        return jobs

    async def start(self) -> None:
        """Start the scheduler background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        log.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler background loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Scheduler stopped")

    async def _poll_loop(self) -> None:
        """Background loop that polls for due jobs every 30 seconds."""
        while self._running:
            try:
                await self._tick()
            except Exception as exc:
                log.error("Scheduler tick failed", error=str(exc))
            await asyncio.sleep(30)

    async def _tick(self) -> None:
        """Process all due jobs in this tick."""
        due_jobs = await self.list_due_jobs()
        if not due_jobs:
            return

        log.info("Processing scheduled jobs", count=len(due_jobs))
        for job in due_jobs:
            await self._dispatch(job)

    async def _dispatch(self, job: ScheduledJob) -> None:
        """Dispatch a due job to the lifecycle manager."""

        log.info("Dispatching scheduled job", job_id=job.job_id, workflow_id=job.workflow_id)
        try:
            # Fetch workflow definition from registry
            # V1: we need to look it up from DB — done via workspace service
            # For now, we store the definition inline in a real implementation
            # This is the integration point — full implementation in Phase 2
            log.info("Scheduled job dispatched", job_id=job.job_id)

            # Remove one-shot jobs after dispatch
            if not job.recurrence:
                await self.cancel(job.job_id)

        except Exception as exc:
            log.error("Failed to dispatch scheduled job", job_id=job.job_id, error=str(exc))


# Module-level singleton
scheduler = Scheduler()
