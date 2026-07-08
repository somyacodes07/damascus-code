"""
Benchmark API — FastAPI Router
=================================
Exposes benchmark management and execution endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.benchmarks.service import benchmark_service
from damascus.shared.database import get_session
from damascus.shared.errors import DamascusError

router = APIRouter(prefix="/api/v1", tags=["benchmarks"])


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class BenchmarkCreate(BaseModel):
    workspace_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    target_types: list[str] = Field(default_factory=lambda: ["WORKFLOW"])
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    dataset_reference: str = ""
    scoring_rules: dict[str, Any] = Field(default_factory=dict)
    scoring_method: str = "DETERMINISTIC"


class RunCreate(BaseModel):
    target_id: str
    target_type: str = "WORKFLOW"
    target_version: int = 1
    experiment_id: str | None = None


class CompareRequest(BaseModel):
    baseline_run_id: str
    candidate_run_id: str


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


def _handle(exc: DamascusError) -> HTTPException:
    m = {"BENCHMARK_NOT_FOUND": 404, "BENCHMARK_RUN_FAILED": 500}
    return HTTPException(
        status_code=m.get(exc.code, 500),
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/benchmarks", status_code=201)
async def create_benchmark(
    body: BenchmarkCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        defn = await benchmark_service.create_definition(
            session,
            workspace_id=body.workspace_id,
            name=body.name,
            description=body.description,
            target_types=body.target_types,
            metrics=body.metrics,
            dataset_reference=body.dataset_reference,
            scoring_rules=body.scoring_rules,
            scoring_method=body.scoring_method,
        )
        return {
            "data": {
                "id": defn.id,
                "name": defn.name,
                "workspace_id": defn.workspace_id,
                "status": defn.status,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/benchmarks")
async def list_benchmarks(
    workspace_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    items, total = await benchmark_service.list_definitions(
        session, workspace_id, page, per_page
    )
    return {
        "data": [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "target_types": d.target_types,
                "scoring_method": d.scoring_method,
                "status": d.status,
            }
            for d in items
        ],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.get("/benchmarks/{benchmark_id}")
async def get_benchmark(
    benchmark_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        defn = await benchmark_service.get_definition(session, benchmark_id)
        return {
            "data": {
                "id": defn.id,
                "name": defn.name,
                "description": defn.description,
                "workspace_id": defn.workspace_id,
                "target_types": defn.target_types,
                "metrics": defn.metrics,
                "scoring_method": defn.scoring_method,
                "scoring_rules": defn.scoring_rules,
                "status": defn.status,
                "created_at": defn.created_at.isoformat(),
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.post("/benchmarks/{benchmark_id}/runs", status_code=201)
async def create_run(
    benchmark_id: str,
    body: RunCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        run = await benchmark_service.create_run(
            session,
            benchmark_id=benchmark_id,
            target_id=body.target_id,
            target_type=body.target_type,
            target_version=body.target_version,
            experiment_id=body.experiment_id,
        )
        return {
            "data": {
                "id": run.id,
                "benchmark_id": benchmark_id,
                "target_id": run.target_id,
                "status": run.status,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/benchmarks/runs/{run_id}")
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        run = await benchmark_service.get_run(session, run_id)
        return {
            "data": {
                "id": run.id,
                "benchmark_id": run.benchmark_id,
                "target_id": run.target_id,
                "target_type": run.target_type,
                "overall_score": run.overall_score,
                "metrics": run.metrics,
                "status": run.status,
                "duration_ms": run.duration_ms,
                "error_message": run.error_message,
                "created_at": run.created_at.isoformat(),
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.post("/benchmarks/compare")
async def compare_runs(
    body: CompareRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = await benchmark_service.compare_runs(
            session, body.baseline_run_id, body.candidate_run_id
        )
        return {"data": result}
    except DamascusError as exc:
        raise _handle(exc) from exc
