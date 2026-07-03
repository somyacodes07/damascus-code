"""
Workspace API — FastAPI Router
================================
Exposes the workspace and workflow CRUD operations as REST endpoints.

Following the API design guidelines from docs:
- Base URL: /api/v1/
- Plural nouns: /workspaces, /workflows
- Consistent response envelope: {"data": ...}
- Pagination: {"data": [...], "pagination": {...}}
- Standard error format: {"error": {"code": ..., "message": ...}}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.core.events.bus import event_bus
from damascus.core.events.types import EventSubject
from damascus.core.lifecycle.manager import get_lifecycle_manager
from damascus.shared.database import get_session
from damascus.shared.errors import (
    DamascusError,
)
from damascus.workspace.models import WorkflowDefinition, Workspace
from damascus.workspace.service import workspace_service

router = APIRouter(prefix="/api/v1", tags=["workspaces"])

# ---------------------------------------------------------------------------
# Pydantic request/response schemas
# ---------------------------------------------------------------------------

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    settings: dict[str, Any] = Field(default_factory=dict)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    settings: dict[str, Any] | None = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str
    settings: dict[str, Any]
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, ws: Workspace) -> WorkspaceResponse:
        return cls(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            owner_id=ws.owner_id,
            settings=ws.settings or {},
            status=ws.status,
            created_at=ws.created_at.isoformat(),
            updated_at=ws.updated_at.isoformat(),
        )


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecuteRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class WorkflowResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    version: int
    status: str
    created_by: str
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, wf: WorkflowDefinition) -> WorkflowResponse:
        return cls(
            id=wf.id,
            workspace_id=wf.workspace_id,
            name=wf.name,
            description=wf.description,
            version=wf.version,
            status=wf.status,
            created_by=wf.created_by,
            created_at=wf.created_at.isoformat(),
            updated_at=wf.updated_at.isoformat(),
        )


# ---------------------------------------------------------------------------
# Error handling helper
# ---------------------------------------------------------------------------

def _handle_error(exc: DamascusError) -> HTTPException:
    status_map = {
        "WORKSPACE_NOT_FOUND": 404,
        "WORKFLOW_NOT_FOUND": 404,
        "WORKSPACE_ALREADY_EXISTS": 409,
        "WORKFLOW_ALREADY_EXISTS": 409,
        "PERMISSION_DENIED": 403,
        "VALIDATION_ERROR": 422,
    }
    status_code = status_map.get(exc.code, 500)
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


# ---------------------------------------------------------------------------
# Workspace endpoints
# ---------------------------------------------------------------------------

@router.get("/workspaces")
async def list_workspaces(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """GET /api/v1/workspaces — List all workspaces."""
    # V1: use a fixed owner_id. Auth is Phase 2+.
    owner_id = "local_user"
    items, total = await workspace_service.list_workspaces(session, owner_id, page, per_page)
    return {
        "data": [WorkspaceResponse.from_orm(ws).model_dump() for ws in items],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.post("/workspaces", status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """POST /api/v1/workspaces — Create a workspace."""
    try:
        workspace = await workspace_service.create_workspace(
            session,
            name=body.name,
            description=body.description,
            owner_id="local_user",
            settings=body.settings,
        )
        await event_bus.publish(
            EventSubject.WORKSPACE_CREATED,
            {"workspace_id": workspace.id, "name": workspace.name},
            workspace_id=workspace.id,
        )
        return {"data": WorkspaceResponse.from_orm(workspace).model_dump()}
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.get("/workspaces/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """GET /api/v1/workspaces/{workspace_id}"""
    try:
        workspace = await workspace_service.get_workspace(session, workspace_id)
        return {"data": WorkspaceResponse.from_orm(workspace).model_dump()}
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """PATCH /api/v1/workspaces/{workspace_id}"""
    try:
        workspace = await workspace_service.update_workspace(
            session,
            workspace_id,
            name=body.name,
            description=body.description,
            settings=body.settings,
        )
        return {"data": WorkspaceResponse.from_orm(workspace).model_dump()}
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.delete("/workspaces/{workspace_id}", status_code=204, response_class=Response)
async def delete_workspace(
    workspace_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """DELETE /api/v1/workspaces/{workspace_id}"""
    try:
        await workspace_service.delete_workspace(session, workspace_id)
        await event_bus.publish(
            EventSubject.WORKSPACE_DELETED,
            {"workspace_id": workspace_id},
            workspace_id=workspace_id,
        )
        return Response(status_code=204)
    except DamascusError as exc:
        raise _handle_error(exc) from exc


# ---------------------------------------------------------------------------
# Workflow endpoints
# ---------------------------------------------------------------------------

@router.get("/workspaces/{workspace_id}/workflows")
async def list_workflows(
    workspace_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """GET /api/v1/workspaces/{workspace_id}/workflows"""
    try:
        items, total = await workspace_service.list_workflows(session, workspace_id, page, per_page)
        return {
            "data": [WorkflowResponse.from_orm(wf).model_dump() for wf in items],
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": max(1, -(-total // per_page)),
            },
        }
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.post("/workspaces/{workspace_id}/workflows", status_code=201)
async def create_workflow(
    workspace_id: str,
    body: WorkflowCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """POST /api/v1/workspaces/{workspace_id}/workflows"""
    try:
        workflow = await workspace_service.create_workflow(
            session,
            workspace_id=workspace_id,
            name=body.name,
            description=body.description,
            nodes=body.nodes,
            edges=body.edges,
            input_schema=body.input_schema,
            output_schema=body.output_schema,
            created_by="local_user",
        )
        await event_bus.publish(
            EventSubject.WORKFLOW_CREATED,
            {"workflow_id": workflow.id, "workspace_id": workspace_id},
            workspace_id=workspace_id,
        )
        return {"data": WorkflowResponse.from_orm(workflow).model_dump()}
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """GET /api/v1/workflows/{workflow_id}"""
    try:
        workflow = await workspace_service.get_workflow(session, workflow_id)
        return {"data": WorkflowResponse.from_orm(workflow).model_dump()}
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.post("/workflows/{workflow_id}/execute", status_code=202)
async def execute_workflow(
    workflow_id: str,
    body: WorkflowExecuteRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """POST /api/v1/workflows/{workflow_id}/execute — Start a workflow execution."""
    try:
        workflow = await workspace_service.get_workflow(session, workflow_id)
        lifecycle = get_lifecycle_manager()

        # Build definition dict for runtime
        definition = {
            "id": workflow.id,
            "name": workflow.name,
            "nodes": workflow.nodes,
            "edges": workflow.edges,
        }

        execution_id = await lifecycle.start_workflow(
            workflow_definition=definition,
            inputs=body.inputs,
            workspace_id=workflow.workspace_id,
        )

        # Record in DB
        await workspace_service.record_execution_start(
            session,
            execution_id=execution_id,
            workflow_id=workflow_id,
            workspace_id=workflow.workspace_id,
            inputs=body.inputs,
        )

        return {"data": {"execution_id": execution_id, "status": "RUNNING"}}
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.post("/executions/{execution_id}/pause")
async def pause_execution(execution_id: str) -> dict[str, Any]:
    """POST /api/v1/executions/{execution_id}/pause"""
    lifecycle = get_lifecycle_manager()
    await lifecycle.pause_workflow(execution_id, workspace_id="")
    return {"data": {"execution_id": execution_id, "status": "PAUSED"}}


@router.post("/executions/{execution_id}/resume")
async def resume_execution(execution_id: str) -> dict[str, Any]:
    """POST /api/v1/executions/{execution_id}/resume"""
    lifecycle = get_lifecycle_manager()
    await lifecycle.resume_workflow(execution_id, workspace_id="")
    return {"data": {"execution_id": execution_id, "status": "RUNNING"}}


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str) -> dict[str, Any]:
    """POST /api/v1/executions/{execution_id}/cancel"""
    lifecycle = get_lifecycle_manager()
    await lifecycle.cancel_workflow(execution_id, workspace_id="")
    return {"data": {"execution_id": execution_id, "status": "CANCELLED"}}
