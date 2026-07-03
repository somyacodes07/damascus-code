"""
Unit tests for the Workspace service.
Uses in-memory SQLite for fast isolated tests.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from damascus.shared.database import Base
from damascus.workspace.service import WorkspaceService
from damascus.shared.errors import WorkspaceNotFoundError, WorkspaceAlreadyExistsError


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
    return WorkspaceService()


@pytest.mark.asyncio
async def test_create_workspace(session, service):
    """Should create a workspace and return it with a proper ID."""
    ws = await service.create_workspace(
        session,
        name="Test Workspace",
        description="A test",
        owner_id="user_1",
    )
    assert ws.id.startswith("ws_")
    assert ws.name == "Test Workspace"
    assert ws.owner_id == "user_1"
    assert ws.status == "ACTIVE"


@pytest.mark.asyncio
async def test_create_duplicate_workspace_raises(session, service):
    """Creating a workspace with the same name for the same owner should raise."""
    await service.create_workspace(session, name="Dupe", owner_id="user_1")
    with pytest.raises(WorkspaceAlreadyExistsError):
        await service.create_workspace(session, name="Dupe", owner_id="user_1")


@pytest.mark.asyncio
async def test_get_workspace_not_found(session, service):
    """Getting a non-existent workspace should raise WorkspaceNotFoundError."""
    with pytest.raises(WorkspaceNotFoundError):
        await service.get_workspace(session, "ws_doesnotexist")


@pytest.mark.asyncio
async def test_update_workspace(session, service):
    """Should update workspace fields."""
    ws = await service.create_workspace(session, name="Original", owner_id="user_1")
    updated = await service.update_workspace(session, ws.id, name="Updated")
    assert updated.name == "Updated"


@pytest.mark.asyncio
async def test_delete_workspace_soft_deletes(session, service):
    """Deleting a workspace should soft-delete it (status=DELETED)."""
    ws = await service.create_workspace(session, name="To Delete", owner_id="user_1")
    await service.delete_workspace(session, ws.id)
    with pytest.raises(WorkspaceNotFoundError):
        await service.get_workspace(session, ws.id)


@pytest.mark.asyncio
async def test_list_workspaces(session, service):
    """Should list workspaces for an owner."""
    await service.create_workspace(session, name="WS 1", owner_id="user_1")
    await service.create_workspace(session, name="WS 2", owner_id="user_1")
    await service.create_workspace(session, name="WS 3", owner_id="user_2")  # Different owner

    items, total = await service.list_workspaces(session, owner_id="user_1")
    assert total == 2
    assert len(items) == 2


@pytest.mark.asyncio
async def test_create_workflow(session, service):
    """Should create a workflow inside a workspace."""
    ws = await service.create_workspace(session, name="WS", owner_id="user_1")
    wf = await service.create_workflow(
        session,
        workspace_id=ws.id,
        name="My Workflow",
        description="A test workflow",
        nodes=[{"id": "node_1", "type": "AGENT"}],
        edges=[],
        created_by="user_1",
    )
    assert wf.id.startswith("wf_")
    assert wf.workspace_id == ws.id
    assert wf.version == 1
