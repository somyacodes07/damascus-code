"""
Research API — FastAPI Router
================================
Exposes research task management endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.research.service import research_service
from damascus.shared.database import get_session
from damascus.shared.errors import DamascusError

router = APIRouter(prefix="/api/v1", tags=["research"])


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class ResearchTaskCreate(BaseModel):
    workspace_id: str
    query: str = Field(..., min_length=1)
    scope: str = "web"
    max_sources: int = Field(default=10, ge=1, le=50)
    output_format: str = "summary"


class FindingCreate(BaseModel):
    finding_type: str = "FACT"
    content: str = Field(..., min_length=1)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_url: str = ""
    source_title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


def _handle(exc: DamascusError) -> HTTPException:
    m = {"RESEARCH_TASK_NOT_FOUND": 404}
    return HTTPException(
        status_code=m.get(exc.code, 500),
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/research/tasks", status_code=201)
async def create_task(
    body: ResearchTaskCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        task = await research_service.create_task(
            session,
            workspace_id=body.workspace_id,
            query=body.query,
            scope=body.scope,
            max_sources=body.max_sources,
            output_format=body.output_format,
        )
        return {
            "data": {
                "id": task.id,
                "query": task.query,
                "status": task.status,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/research/tasks/{task_id}")
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        task = await research_service.get_task(session, task_id)
        return {
            "data": {
                "id": task.id,
                "query": task.query,
                "scope": task.scope,
                "status": task.status,
                "result_summary": task.result_summary,
                "error_message": task.error_message,
                "finding_count": len(task.findings),
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/research/tasks")
async def list_tasks(
    workspace_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    items, total = await research_service.list_tasks(
        session, workspace_id, page, per_page
    )
    return {
        "data": [
            {
                "id": t.id,
                "query": t.query,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in items
        ],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.post("/research/tasks/{task_id}/findings", status_code=201)
async def add_finding(
    task_id: str,
    body: FindingCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        finding = await research_service.add_finding(
            session,
            task_id=task_id,
            finding_type=body.finding_type,
            content=body.content,
            relevance_score=body.relevance_score,
            source_url=body.source_url,
            source_title=body.source_title,
            metadata=body.metadata,
        )
        return {
            "data": {
                "id": finding.id,
                "finding_type": finding.finding_type,
                "relevance_score": finding.relevance_score,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/research/tasks/{task_id}/findings")
async def get_findings(
    task_id: str,
    min_relevance: float = Query(default=0.0, ge=0.0, le=1.0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        findings = await research_service.get_findings(
            session, task_id, min_relevance=min_relevance
        )
        return {
            "data": [
                {
                    "id": f.id,
                    "finding_type": f.finding_type,
                    "content": f.content,
                    "relevance_score": f.relevance_score,
                    "source_url": f.source_url,
                    "source_title": f.source_title,
                }
                for f in findings
            ]
        }
    except DamascusError as exc:
        raise _handle(exc) from exc
