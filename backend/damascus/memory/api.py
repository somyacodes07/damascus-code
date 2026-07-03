"""
Memory API — FastAPI Router
============================
Exposes memory storage and retrieval endpoints.

Endpoints:
  GET    /api/v1/memories?workspace_id=&query=  — Search memories
  POST   /api/v1/memories                       — Store a memory
  GET    /api/v1/memories/{id}                  — Get a memory
  DELETE /api/v1/memories/{id}                  — Delete a memory
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.memory.models import MemorySource, MemoryType
from damascus.memory.service import memory_service
from damascus.shared.database import get_session
from damascus.shared.errors import DamascusError

router = APIRouter(prefix="/api/v1", tags=["memory"])


class MemoryCreate(BaseModel):
    workspace_id: str
    content: str = Field(..., min_length=1)
    summary: str = Field(default="")
    memory_type: MemoryType = MemoryType.EPISODIC
    source_type: MemorySource = MemorySource.WORKFLOW
    source_id: str = ""
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    id: str
    workspace_id: str
    type: str
    content: str
    summary: str
    source_type: str
    tags: list[str]
    importance: float
    created_at: str
    accessed_at: str
    access_count: int


def _handle_error(exc: DamascusError) -> HTTPException:
    status_map = {"MEMORY_NOT_FOUND": 404}
    return HTTPException(
        status_code=status_map.get(exc.code, 500),
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


@router.get("/memories")
async def search_memories(
    workspace_id: str = Query(...),
    query: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Search memories by semantic similarity or list all."""
    if query:
        results = await memory_service.search(
            session,
            workspace_id=workspace_id,
            query=query,
            limit=per_page,
        )
        return {"data": results, "pagination": {"total": len(results), "page": page, "per_page": per_page, "total_pages": 1}}
    else:
        items, total = await memory_service.list_for_workspace(session, workspace_id, page, per_page)
        data = [
            {
                "id": m.id,
                "workspace_id": m.workspace_id,
                "type": m.type,
                "content": m.content[:500],
                "summary": m.summary,
                "source_type": m.source_type,
                "tags": m.tags,
                "importance": m.importance,
                "created_at": m.created_at.isoformat(),
            }
            for m in items
        ]
        return {
            "data": data,
            "pagination": {"total": total, "page": page, "per_page": per_page, "total_pages": max(1, -(-total // per_page))},
        }


@router.post("/memories", status_code=201)
async def store_memory(
    body: MemoryCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Store a new memory record."""
    try:
        record = await memory_service.store(
            session,
            workspace_id=body.workspace_id,
            content=body.content,
            summary=body.summary,
            memory_type=body.memory_type,
            source_type=body.source_type,
            source_id=body.source_id,
            tags=body.tags,
            importance=body.importance,
        )
        return {
            "data": {
                "id": record.id,
                "workspace_id": record.workspace_id,
                "type": record.type,
                "summary": record.summary,
                "embedding_id": record.embedding_id,
                "created_at": record.created_at.isoformat(),
            }
        }
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.get("/memories/{memory_id}")
async def get_memory(
    memory_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get a single memory record."""
    try:
        record = await memory_service.get(session, memory_id)
        return {
            "data": {
                "id": record.id,
                "workspace_id": record.workspace_id,
                "type": record.type,
                "content": record.content,
                "summary": record.summary,
                "source_type": record.source_type,
                "tags": record.tags,
                "importance": record.importance,
                "confidence": record.confidence,
                "embedding_id": record.embedding_id,
                "created_at": record.created_at.isoformat(),
                "accessed_at": record.accessed_at.isoformat(),
                "access_count": record.access_count,
            }
        }
    except DamascusError as exc:
        raise _handle_error(exc) from exc


@router.delete("/memories/{memory_id}", status_code=204, response_class=Response)
async def delete_memory(
    memory_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete a memory record."""
    try:
        await memory_service.delete(session, memory_id)
        return Response(status_code=204)
    except DamascusError as exc:
        raise _handle_error(exc) from exc
