"""
API Client — HTTP client for Damascus backend
==============================================
All CLI commands call the backend through this client.
Uses httpx for async HTTP requests.

Default backend URL: http://localhost:8000
Override with DAMASCUS_API_URL environment variable.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_DEFAULT_URL = os.getenv("DAMASCUS_API_URL", "http://localhost:8000")
_TIMEOUT = 30.0


class DamascusClient:
    """Thin HTTP client wrapping the Damascus backend REST API."""

    def __init__(self, base_url: str = _DEFAULT_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=_TIMEOUT)

    async def __aenter__(self) -> "DamascusClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        resp = await self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Workspaces
    # ------------------------------------------------------------------

    async def list_workspaces(self, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        resp = await self._client.get("/api/v1/workspaces", params={"page": page, "per_page": per_page})
        resp.raise_for_status()
        return resp.json()

    async def create_workspace(self, name: str, description: str = "") -> dict[str, Any]:
        resp = await self._client.post("/api/v1/workspaces", json={"name": name, "description": description})
        resp.raise_for_status()
        return resp.json()

    async def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/api/v1/workspaces/{workspace_id}")
        resp.raise_for_status()
        return resp.json()

    async def delete_workspace(self, workspace_id: str) -> None:
        resp = await self._client.delete(f"/api/v1/workspaces/{workspace_id}")
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Workflows
    # ------------------------------------------------------------------

    async def list_workflows(self, workspace_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/api/v1/workspaces/{workspace_id}/workflows")
        resp.raise_for_status()
        return resp.json()

    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self._client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            json={"inputs": inputs or {}},
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    async def search_memories(self, workspace_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        resp = await self._client.get(
            "/api/v1/memories",
            params={"workspace_id": workspace_id, "query": query, "per_page": limit},
        )
        resp.raise_for_status()
        return resp.json()

    async def list_memories(self, workspace_id: str, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        resp = await self._client.get(
            "/api/v1/memories",
            params={"workspace_id": workspace_id, "page": page, "per_page": per_page},
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    async def list_models(self) -> dict[str, Any]:
        resp = await self._client.get("/api/v1/models")
        resp.raise_for_status()
        return resp.json()


# Synchronous context manager for use in Typer commands
import asyncio


def run_async(coro: Any) -> Any:
    """Run an async function from a synchronous Typer command."""
    return asyncio.run(coro)
