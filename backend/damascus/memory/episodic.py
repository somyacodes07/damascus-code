"""
Episodic Memory — PostgreSQL-backed
=====================================
Episodic memory stores completed workflow records, agent interactions,
and the narrative history of what Damascus has done.

Episodic memories are durable, workspace-scoped, and searchable.
They serve as the authoritative record of events that occurred.

Storage: PostgreSQL (MemoryRecord table with type=EPISODIC)
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.memory.models import MemoryRecord, MemorySource, MemoryStatus, MemoryType
from damascus.shared.errors import MemoryNotFoundError

log = structlog.get_logger(__name__)


class EpisodicMemory:
    """
    Stores and retrieves episodic memories in PostgreSQL.
    Episodic memories = what happened, when, and what was learned.
    """

    async def store(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        content: str,
        summary: str = "",
        source_type: MemorySource = MemorySource.WORKFLOW,
        source_id: str = "",
        tags: list[str] | None = None,
        importance: float = 0.5,
    ) -> MemoryRecord:
        """Store a new episodic memory record."""
        record = MemoryRecord(
            workspace_id=workspace_id,
            type=MemoryType.EPISODIC,
            content=content,
            summary=summary or content[:200],
            source_type=source_type,
            source_id=source_id,
            tags=tags or [],
            importance=importance,
        )
        session.add(record)
        await session.flush()
        log.info("Stored episodic memory", memory_id=record.id, workspace_id=workspace_id)
        return record

    async def get(self, session: AsyncSession, memory_id: str) -> MemoryRecord:
        """Retrieve a memory record by ID."""
        record = await session.get(MemoryRecord, memory_id)
        if record is None:
            raise MemoryNotFoundError(memory_id=memory_id)
        # Update access tracking
        record.accessed_at = datetime.now(UTC)
        record.access_count += 1
        await session.flush()
        return record

    async def list_for_workspace(
        self,
        session: AsyncSession,
        workspace_id: str,
        page: int = 1,
        per_page: int = 20,
        tags: list[str] | None = None,
    ) -> tuple[list[MemoryRecord], int]:
        """List episodic memories for a workspace."""
        from sqlalchemy import func

        base_stmt = select(MemoryRecord).where(
            MemoryRecord.workspace_id == workspace_id,
            MemoryRecord.type == MemoryType.EPISODIC,
            MemoryRecord.status == MemoryStatus.ACTIVE,
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = await session.scalar(count_stmt) or 0

        stmt = (
            base_stmt
            .order_by(MemoryRecord.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await session.scalars(stmt)
        return list(result.all()), total

    async def archive(self, session: AsyncSession, memory_id: str) -> None:
        """Archive an episodic memory (soft-delete)."""
        record = await session.get(MemoryRecord, memory_id)
        if record:
            record.status = MemoryStatus.ARCHIVED
            record.updated_at = datetime.now(UTC)
            await session.flush()


# Module-level singleton
episodic_memory = EpisodicMemory()
