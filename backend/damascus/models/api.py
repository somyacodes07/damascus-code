"""
Models API — FastAPI Router
============================
Exposes model generation and provider listing endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from damascus.models.interface import ModelRequest
from damascus.models.service import model_service
from damascus.shared.errors import DamascusError

router = APIRouter(prefix="/api/v1", tags=["models"])


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system_prompt: str = ""
    model: str = ""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=32768)
    messages: list[dict[str, str]] = Field(default_factory=list)


@router.get("/models")
async def list_models() -> dict[str, Any]:
    """GET /api/v1/models — List available models by provider."""
    models = await model_service.list_available_models()
    return {"data": models}


@router.get("/models/health")
async def provider_health() -> dict[str, Any]:
    """GET /api/v1/models/health — Check provider availability."""
    status = await model_service.health()
    return {"data": status}


@router.post("/models/generate")
async def generate(body: GenerateRequest) -> dict[str, Any]:
    """POST /api/v1/models/generate — Generate a completion."""
    try:
        request = ModelRequest(
            prompt=body.prompt,
            system_prompt=body.system_prompt,
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            messages=body.messages,
        )
        response = await model_service.generate(request)
        return {
            "data": {
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.total_tokens,
                },
                "finish_reason": response.finish_reason,
            }
        }
    except DamascusError as exc:
        raise HTTPException(status_code=503, detail={"error": {"code": exc.code, "message": exc.message}}) from exc
