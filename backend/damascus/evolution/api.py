"""
Evolution API — FastAPI Router
=================================
Exposes the evolution engine through REST endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from damascus.evolution.service import evolution_service
from damascus.shared.database import get_session
from damascus.shared.errors import DamascusError

router = APIRouter(prefix="/api/v1", tags=["evolution"])


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class ExperimentCreate(BaseModel):
    workspace_id: str
    name: str = Field(..., min_length=1, max_length=255)
    hypothesis: str = ""
    target_type: str = "WORKFLOW"
    target_id: str
    baseline_id: str
    benchmark_suite_id: str
    metrics_to_compare: list[str] = Field(default_factory=list)
    resource_budget: dict[str, Any] = Field(default_factory=dict)
    safety_constraints: list[str] = Field(default_factory=list)
    opportunity_id: str | None = None


class GenerateVariantsRequest(BaseModel):
    baseline_config: dict[str, Any]
    available_models: list[str] = Field(default_factory=list)


class PromotionApproval(BaseModel):
    approver_id: str


class PromotionRejection(BaseModel):
    rejector_id: str
    reason: str = ""


class RollbackRequest(BaseModel):
    cause: str
    evidence: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


def _handle(exc: DamascusError) -> HTTPException:
    m = {
        "EXPERIMENT_NOT_FOUND": 404,
        "EXPERIMENT_ALREADY_RUNNING": 409,
        "PROMOTION_NOT_FOUND": 404,
        "ROLLBACK_FAILED": 500,
        "SAFETY_CONSTRAINT_VIOLATION": 403,
    }
    return HTTPException(
        status_code=m.get(exc.code, 500),
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


# ---------------------------------------------------------------------------
# Opportunity Endpoints
# ---------------------------------------------------------------------------


@router.post("/evolution/opportunities/analyze")
async def analyze_opportunities(
    workspace_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Analyze a workspace for improvement opportunities."""
    try:
        opportunities = await evolution_service.analyze_opportunities(
            session, workspace_id
        )
        return {"data": opportunities, "count": len(opportunities)}
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/evolution/opportunities")
async def list_opportunities(
    workspace_id: str = Query(...),
    include_addressed: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    opps = await evolution_service.list_opportunities(
        session, workspace_id, include_addressed=include_addressed
    )
    return {
        "data": [
            {
                "id": o.id,
                "target_id": o.target_id,
                "target_type": o.target_type,
                "opportunity_type": o.opportunity_type,
                "description": o.description,
                "priority_score": o.priority_score,
                "addressed": o.addressed,
                "created_at": o.created_at.isoformat(),
            }
            for o in opps
        ]
    }


# ---------------------------------------------------------------------------
# Experiment Endpoints
# ---------------------------------------------------------------------------


@router.post("/evolution/experiments", status_code=201)
async def create_experiment(
    body: ExperimentCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        exp = await evolution_service.create_experiment(
            session,
            workspace_id=body.workspace_id,
            name=body.name,
            hypothesis=body.hypothesis,
            target_type=body.target_type,
            target_id=body.target_id,
            baseline_id=body.baseline_id,
            benchmark_suite_id=body.benchmark_suite_id,
            metrics_to_compare=body.metrics_to_compare,
            resource_budget=body.resource_budget,
            safety_constraints=body.safety_constraints,
            opportunity_id=body.opportunity_id,
        )
        return {
            "data": {
                "id": exp.id,
                "name": exp.name,
                "status": exp.status,
                "target_id": exp.target_id,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/evolution/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        exp = await evolution_service.get_experiment(session, experiment_id)
        return {
            "data": {
                "id": exp.id,
                "name": exp.name,
                "hypothesis": exp.hypothesis,
                "target_type": exp.target_type,
                "target_id": exp.target_id,
                "baseline_id": exp.baseline_id,
                "status": exp.status,
                "created_at": exp.created_at.isoformat(),
                "variants": [
                    {
                        "id": v.id,
                        "name": v.name,
                        "status": v.status,
                        "score": v.score,
                    }
                    for v in exp.variants
                ],
                "promotions": [
                    {
                        "id": p.id,
                        "variant_id": p.variant_id,
                        "status": p.status,
                    }
                    for p in exp.promotions
                ],
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.get("/evolution/experiments")
async def list_experiments(
    workspace_id: str = Query(...),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    items, total = await evolution_service.list_experiments(
        session, workspace_id, page, per_page
    )
    return {
        "data": [
            {
                "id": e.id,
                "name": e.name,
                "status": e.status,
                "target_id": e.target_id,
                "variant_count": len(e.variants),
                "created_at": e.created_at.isoformat(),
            }
            for e in items
        ],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


# ---------------------------------------------------------------------------
# Variant Endpoints
# ---------------------------------------------------------------------------


@router.post("/evolution/experiments/{experiment_id}/variants", status_code=201)
async def generate_variants(
    experiment_id: str,
    body: GenerateVariantsRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        variants = await evolution_service.generate_variants(
            session,
            experiment_id,
            baseline_config=body.baseline_config,
            available_models=body.available_models or None,
        )
        return {
            "data": [
                {
                    "id": v.id,
                    "name": v.name,
                    "hypothesis": v.hypothesis,
                    "change_set": v.change_set,
                    "status": v.status,
                }
                for v in variants
            ],
            "count": len(variants),
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


# ---------------------------------------------------------------------------
# Promotion Endpoints
# ---------------------------------------------------------------------------


@router.post("/evolution/promotions/{promotion_id}/approve")
async def approve_promotion(
    promotion_id: str,
    body: PromotionApproval,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        record = await evolution_service.approve_promotion(
            session, promotion_id, body.approver_id
        )
        return {
            "data": {
                "id": record.id,
                "status": record.status,
                "approved_by": record.approved_by,
                "variant_id": record.variant_id,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.post("/evolution/promotions/{promotion_id}/reject")
async def reject_promotion(
    promotion_id: str,
    body: PromotionRejection,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        record = await evolution_service.reject_promotion(
            session, promotion_id, body.rejector_id, body.reason
        )
        return {
            "data": {
                "id": record.id,
                "status": record.status,
                "variant_id": record.variant_id,
            }
        }
    except DamascusError as exc:
        raise _handle(exc) from exc


@router.post("/evolution/promotions/{promotion_id}/rollback")
async def rollback_promotion(
    promotion_id: str,
    body: RollbackRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = await evolution_service.rollback_promotion(
            session, promotion_id, body.cause, body.evidence
        )
        return {"data": result}
    except DamascusError as exc:
        raise _handle(exc) from exc


# ---------------------------------------------------------------------------
# Lineage Endpoints
# ---------------------------------------------------------------------------


@router.get("/evolution/lineage/{target_id}")
async def get_lineage(
    target_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    lineage = await evolution_service.get_lineage(session, target_id)
    return {"data": lineage}
