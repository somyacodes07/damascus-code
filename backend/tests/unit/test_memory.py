"""
Unit tests for the Memory service.
Uses in-memory SQLite for fast isolated tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from damascus.memory.models import MemorySource, MemoryType
from damascus.memory.service import MemoryService
from damascus.shared.database import Base
from damascus.shared.errors import MemoryNotFoundError


@pytest.fixture
async def session():
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


@pytest.fixture
def service():
    return MemoryService()


@pytest.mark.asyncio
async def test_store_episodic_memory(session, service):
    """Should store an episodic memory and return a record with valid ID."""
    with patch("damascus.memory.semantic.SemanticMemory.store_embedding", new_callable=AsyncMock, return_value=None):
        with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
            record = await service.store(
                session,
                workspace_id="ws_test001",
                content="The agent completed the research task in 45 seconds.",
                summary="Research task completed",
                memory_type=MemoryType.EPISODIC,
                source_type=MemorySource.WORKFLOW,
                source_id="exec_abc123",
                tags=["research", "completed"],
                importance=0.8,
            )

    assert record.id.startswith("mem_")
    assert record.workspace_id == "ws_test001"
    assert record.content == "The agent completed the research task in 45 seconds."
    assert record.source_id == "exec_abc123"
    assert record.importance == 0.8
    assert "research" in record.tags


@pytest.mark.asyncio
async def test_get_memory_increments_access_count(session, service):
    """Retrieving a memory should increment its access count."""
    with patch("damascus.memory.semantic.SemanticMemory.store_embedding", new_callable=AsyncMock, return_value=None):
        with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
            record = await service.store(
                session,
                workspace_id="ws_test001",
                content="Test memory",
            )

    with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
        fetched = await service.get(session, record.id)

    assert fetched.access_count == 1

    with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
        fetched2 = await service.get(session, record.id)

    assert fetched2.access_count == 2


@pytest.mark.asyncio
async def test_get_nonexistent_memory_raises(session, service):
    """Getting a non-existent memory should raise MemoryNotFoundError."""
    with pytest.raises(MemoryNotFoundError):
        await service.get(session, "mem_doesnotexist")


@pytest.mark.asyncio
async def test_list_memories_for_workspace(session, service):
    """Should list all memories for a workspace."""
    with patch("damascus.memory.semantic.SemanticMemory.store_embedding", new_callable=AsyncMock, return_value=None):
        with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
            await service.store(session, workspace_id="ws_001", content="Memory A")
            await service.store(session, workspace_id="ws_001", content="Memory B")
            await service.store(session, workspace_id="ws_002", content="Memory C")

    items, total = await service.list_for_workspace(session, "ws_001")
    assert total == 2
    assert len(items) == 2


@pytest.mark.asyncio
async def test_delete_memory(session, service):
    """Deleting a memory should archive it and remove from search."""
    with patch("damascus.memory.semantic.SemanticMemory.store_embedding", new_callable=AsyncMock, return_value=None):
        with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
            record = await service.store(session, workspace_id="ws_001", content="To be deleted")

    with patch("damascus.memory.semantic.SemanticMemory.delete_embedding", new_callable=AsyncMock):
        await service.delete(session, record.id)

    # After deletion, the record should not be found in active list
    items, total = await service.list_for_workspace(session, "ws_001")
    assert total == 0


@pytest.mark.asyncio
async def test_memory_importance_range(session, service):
    """Importance must be between 0.0 and 1.0."""
    with patch("damascus.memory.semantic.SemanticMemory.store_embedding", new_callable=AsyncMock, return_value=None):
        with patch("damascus.core.events.bus.EventBus.publish", new_callable=AsyncMock):
            record = await service.store(
                session,
                workspace_id="ws_001",
                content="Critical memory",
                importance=1.0,
            )
    assert record.importance == 1.0
