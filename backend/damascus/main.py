"""
Damascus FastAPI Application
=============================
Entry point for the Damascus backend.

Architecture:
  - Startup: connects to all infrastructure services
  - Lifespan: manages connection lifecycle (open/close)
  - Routers: mounts all subsystem API routers
  - Health: exposes /health endpoint for monitoring
  - Metrics: exposes /metrics endpoint for Prometheus

Start with:
  uvicorn damascus.main:app --reload --port 8000
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from damascus.config import settings
from damascus.core.observability.telemetry import configure_logging, metrics_app

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Application startup / shutdown lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    AsyncContextManager for FastAPI lifespan events.
    Connects to all infrastructure on startup, closes connections on shutdown.
    """
    # --- STARTUP ---
    configure_logging(settings.observability.log_level)
    log.info(
        "Starting Damascus",
        version="0.1.0",
        environment=settings.env,
        debug=settings.debug,
    )

    # Connect to infrastructure services
    startup_errors: list[str] = []

    # PostgreSQL
    try:
        from damascus.shared.database import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        log.info("PostgreSQL connected")
    except Exception as exc:
        startup_errors.append(f"PostgreSQL: {exc}")
        log.error("PostgreSQL connection failed", error=str(exc))

    # Redis
    try:
        from damascus.shared.cache import ping_redis

        if await ping_redis():
            log.info("Redis connected")
        else:
            startup_errors.append("Redis: ping failed")
    except Exception as exc:
        startup_errors.append(f"Redis: {exc}")
        log.error("Redis connection failed", error=str(exc))

    # Qdrant
    try:
        from damascus.shared.vector import ensure_collections, ping_qdrant

        if await ping_qdrant():
            await ensure_collections()
            log.info("Qdrant connected and collections initialized")
        else:
            startup_errors.append("Qdrant: ping failed")
    except Exception as exc:
        startup_errors.append(f"Qdrant: {exc}")
        log.warning("Qdrant connection failed (non-critical for Phase 1)", error=str(exc))

    # NATS
    try:
        from damascus.shared.messaging import ping_nats

        if await ping_nats():
            log.info("NATS connected")
        else:
            startup_errors.append("NATS: ping failed")
    except Exception as exc:
        startup_errors.append(f"NATS: {exc}")
        log.warning("NATS connection failed (non-critical for Phase 1)", error=str(exc))

    # MinIO
    try:
        from damascus.shared.storage import ensure_buckets, ping_storage

        if ping_storage():
            await ensure_buckets()
            log.info("MinIO connected and buckets initialized")
        else:
            startup_errors.append("MinIO: ping failed")
    except Exception as exc:
        startup_errors.append(f"MinIO: {exc}")
        log.warning("MinIO connection failed (non-critical for Phase 1)", error=str(exc))

    if startup_errors and settings.is_production:
        log.error("Critical startup errors in production", errors=startup_errors)
        raise RuntimeError(f"Failed to connect to required services: {startup_errors}")

    log.info("Damascus started successfully", warnings=startup_errors or None)

    yield  # Application runs here

    # --- SHUTDOWN ---
    log.info("Shutting down Damascus...")

    try:
        from damascus.shared.database import close_engine

        await close_engine()
    except Exception as exc:
        log.warning("Error closing PostgreSQL", error=str(exc))

    try:
        from damascus.shared.cache import close_redis

        await close_redis()
    except Exception as exc:
        log.warning("Error closing Redis", error=str(exc))

    try:
        from damascus.shared.messaging import close_nats

        await close_nats()
    except Exception as exc:
        log.warning("Error closing NATS", error=str(exc))

    try:
        from damascus.shared.vector import close_qdrant

        await close_qdrant()
    except Exception as exc:
        log.warning("Error closing Qdrant", error=str(exc))

    log.info("Damascus shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Damascus",
    description="Intelligence Operating System — Phase 2 API",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS — allow all origins in development, tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Prometheus metrics endpoint
# ---------------------------------------------------------------------------
app.mount("/metrics", metrics_app)

# ---------------------------------------------------------------------------
# API Routers — mount all subsystems
# ---------------------------------------------------------------------------

from damascus.agents.api import router as agents_router
from damascus.benchmarks.api import router as benchmarks_router
from damascus.evolution.api import router as evolution_router
from damascus.memory.api import router as memory_router
from damascus.models.api import router as models_router
from damascus.research.api import router as research_router
from damascus.tools.api import router as tools_router
from damascus.workspace.api import router as workspace_router

# Phase 1 routers
app.include_router(workspace_router)
app.include_router(memory_router)
app.include_router(agents_router)
app.include_router(models_router)
app.include_router(tools_router)

# Phase 2 routers
app.include_router(benchmarks_router)
app.include_router(evolution_router)
app.include_router(research_router)

# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------

_start_time = time.time()


@app.get("/health", tags=["health"])
async def health() -> dict[str, Any]:
    """
    GET /health — System health check.

    Success criteria (from roadmap Milestone 1.1):
    - Returns "healthy" when all core services are up
    - Used by Docker health checks and monitoring
    """
    checks: dict[str, Any] = {
        "status": "healthy",
        "version": "0.2.0",
        "environment": settings.env,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "services": {},
    }

    # Check Redis
    try:
        from damascus.shared.cache import ping_redis

        checks["services"]["redis"] = "healthy" if await ping_redis() else "unhealthy"
    except Exception:
        checks["services"]["redis"] = "unhealthy"

    # Check Qdrant
    try:
        from damascus.shared.vector import ping_qdrant

        checks["services"]["qdrant"] = "healthy" if await ping_qdrant() else "unhealthy"
    except Exception:
        checks["services"]["qdrant"] = "unhealthy"

    # Check NATS
    try:
        from damascus.shared.messaging import ping_nats

        checks["services"]["nats"] = "healthy" if await ping_nats() else "unhealthy"
    except Exception:
        checks["services"]["nats"] = "unhealthy"

    # Check MinIO
    try:
        from damascus.shared.storage import ping_storage

        checks["services"]["minio"] = "healthy" if ping_storage() else "unhealthy"
    except Exception:
        checks["services"]["minio"] = "unhealthy"

    # Check model providers
    try:
        from damascus.models.service import model_service

        provider_health = await model_service.health()
        checks["services"]["models"] = provider_health
    except Exception:
        checks["services"]["models"] = {}

    # Mark as degraded if any service is unhealthy
    unhealthy = [k for k, v in checks["services"].items() if v == "unhealthy"]
    if unhealthy:
        checks["status"] = "degraded"
        checks["unhealthy_services"] = unhealthy

    return checks


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint — redirects to API docs."""
    return {"message": "Damascus API v0.2. See /docs for API documentation."}
