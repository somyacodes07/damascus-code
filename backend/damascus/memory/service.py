"""
Memory Service — Unified Memory Layer V1
==========================================
Provides the public API for storing and retrieving memories.
Coordinates between Working Memory (Redis), Episodic Memory (PostgreSQL),
and Semantic Memory (Qdrant).

This is the single entry point for all memory operations.
Subsystems (agents, workflows) call this service — they do NOT call
the individual working/episodic/semantic modules directly.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.core.events.bus import event_bus
from damascus.core.events.types import EventSubject
from damascus.memory.episodic import episodic_memory
from damascus.memory.models import MemoryRecord, MemorySource, MemoryType
from damascus.memory.semantic import semantic_memory
from damascus.shared.errors import MemoryNotFoundError

log = structlog.get_logger(__name__)


class MemoryService:
    """
    Unified Memory Layer V1.

    Responsibilities:
    - Route memory operations to the correct storage backend
    - Ensure working memory transitions to episodic memory after completion
    - Trigger semantic indexing for searchable memories
    - Publish memory events to the event bus
    """

    async def store(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        content: str,
        summary: str = "",
        memory_type: MemoryType = MemoryType.EPISODIC,
        source_type: MemorySource = MemorySource.WORKFLOW,
        source_id: str = "",
        tags: list[str] | None = None,
        importance: float = 0.5,
        index_semantically: bool = True,
    ) -> MemoryRecord:
        """
        Store a new memory record.

        1. Persist to PostgreSQL (episodic store)
        2. Generate vector embedding and store in Qdrant (if enabled)
        3. Publish MemoryStored event
        """
        record = await episodic_memory.store(
            session,
            workspace_id=workspace_id,
            content=content,
            summary=summary,
            source_type=source_type,
            source_id=source_id,
            tags=tags,
            importance=importance,
        )
        record.type = memory_type

        # Semantic indexing
        if index_semantically:
            embedding_id = await semantic_memory.store_embedding(
                memory_id=record.id,
                workspace_id=workspace_id,
                text=f"{summary}\n\n{content}" if summary else content,
                metadata={"source_type": source_type, "tags": tags or []},
            )
            if embedding_id:
                record.embedding_id = embedding_id
                await session.flush()

        await event_bus.publish(
            EventSubject.MEMORY_STORED,
            {"memory_id": record.id, "workspace_id": workspace_id, "type": memory_type},
            workspace_id=workspace_id,
        )

        log.info("Stored memory", memory_id=record.id, workspace_id=workspace_id, type=memory_type)
        return record

    async def search(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Search memories by semantic similarity.
        Returns a ranked list of relevant memory records.

        Steps:
        1. Generate embedding for the query
        2. Search Qdrant for similar memories
        3. Fetch full records from PostgreSQL
        """
        # Semantic search via Qdrant
        hits = await semantic_memory.search(
            workspace_id=workspace_id,
            query=query,
            limit=limit,
            score_threshold=score_threshold,
        )

        # Enrich with full records from DB
        results = []
        for hit in hits:
            memory_id = hit.get("memory_id")
            if memory_id:
                try:
                    record = await episodic_memory.get(session, memory_id)
                    results.append(
                        {
                            "memory_id": record.id,
                            "score": hit["score"],
                            "content": record.content,
                            "summary": record.summary,
                            "type": record.type,
                            "source_type": record.source_type,
                            "tags": record.tags,
                            "importance": record.importance,
                            "created_at": record.created_at.isoformat(),
                        }
                    )
                except MemoryNotFoundError:
                    pass

        await event_bus.publish(
            EventSubject.MEMORY_RETRIEVED,
            {
                "workspace_id": workspace_id,
                "query_length": len(query),
                "results_count": len(results),
            },
            workspace_id=workspace_id,
        )

        return results

    async def get(self, session: AsyncSession, memory_id: str) -> MemoryRecord:
        """Retrieve a single memory record by ID."""
        return await episodic_memory.get(session, memory_id)

    async def list_for_workspace(
        self,
        session: AsyncSession,
        workspace_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[MemoryRecord], int]:
        """List all memories in a workspace (paginated)."""
        return await episodic_memory.list_for_workspace(session, workspace_id, page, per_page)

    async def delete(self, session: AsyncSession, memory_id: str) -> None:
        """
        Delete a memory record.
        Archives the PostgreSQL record and removes the Qdrant embedding.
        """
        record = await episodic_memory.get(session, memory_id)
        if record.embedding_id:
            await semantic_memory.delete_embedding(record.embedding_id)
        await episodic_memory.archive(session, memory_id)
        log.info("Deleted memory", memory_id=memory_id)


# Module-level singleton
memory_service = MemoryService()
