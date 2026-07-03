"""
Integration test: Health endpoint
===================================
Requires a running backend (uvicorn). Skip if not available.
Run with: pytest tests/integration/ --integration
"""

from __future__ import annotations

import pytest
import httpx

BACKEND_URL = "http://localhost:8000"


@pytest.fixture
def skip_if_no_backend():
    """Skip test if backend is not running."""
    try:
        import httpx as hx
        with hx.Client(timeout=2.0) as client:
            client.get(f"{BACKEND_URL}/health")
    except Exception:
        pytest.skip("Backend not running — start with: cd backend && poetry run uvicorn damascus.main:app --reload")


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(skip_if_no_backend):
    """Health endpoint should return 200 with a status field."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=5.0) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "version" in data
    assert "services" in data


@pytest.mark.asyncio
async def test_root_endpoint(skip_if_no_backend):
    """Root endpoint should return a JSON message."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=5.0) as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "message" in resp.json()


@pytest.mark.asyncio
async def test_api_docs_reachable(skip_if_no_backend):
    """OpenAPI docs should be reachable at /docs."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=5.0) as client:
        resp = await client.get("/docs")
    assert resp.status_code == 200
