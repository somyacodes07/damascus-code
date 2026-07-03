#!/usr/bin/env python3
"""
Damascus Setup Verification Script
=====================================
Run this script to verify your development environment is correctly configured.

Usage:
  python scripts/verify_setup.py
  just verify
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

try:
    import httpx
    import redis.asyncio as aioredis
except ImportError:
    print("❌ Required packages not installed. Run: cd backend && poetry install")
    sys.exit(1)

BACKEND_URL = "http://localhost:8000"
REDIS_URL = "redis://localhost:6379"
QDRANT_URL = "http://localhost:6333"
POSTGRES_URL = "postgresql+asyncpg://damascus:damascus_dev@localhost:5432/damascus"


async def check_backend() -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "unknown")
                return True, status
            return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)


async def check_redis() -> tuple[bool, str]:
    try:
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        result = await client.ping()
        await client.aclose()
        return result, "PONG" if result else "No response"
    except Exception as exc:
        return False, str(exc)


async def check_qdrant() -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{QDRANT_URL}/healthz")
            return resp.status_code == 200, resp.text[:50]
    except Exception as exc:
        return False, str(exc)


async def check_postgres() -> tuple[bool, str]:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        engine = create_async_engine(POSTGRES_URL, echo=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True, "Connected"
    except Exception as exc:
        return False, str(exc)


async def check_ollama() -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return True, f"{len(models)} model(s): {', '.join(models[:3])}"
            return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, f"Not running ({exc})"


async def main() -> None:
    print("\n╔═══════════════════════════════════════╗")
    print("║    Damascus Setup Verification V1     ║")
    print("╚═══════════════════════════════════════╝\n")

    checks = [
        ("Backend API (FastAPI)", check_backend()),
        ("PostgreSQL", check_postgres()),
        ("Redis", check_redis()),
        ("Qdrant (Vector DB)", check_qdrant()),
        ("Ollama (Local Models)", check_ollama()),
    ]

    results = await asyncio.gather(*[c[1] for c in checks])

    all_critical_pass = True
    critical = {"Backend API (FastAPI)", "PostgreSQL", "Redis"}
    optional = {"Qdrant (Vector DB)", "Ollama (Local Models)"}

    for (name, _), (ok, detail) in zip(checks, results):
        icon = "✓" if ok else "✗"
        marker = "(CRITICAL)" if name in critical and not ok else "(optional)" if name in optional and not ok else ""
        print(f"  {icon}  {name:<30} {detail}  {marker}")
        if name in critical and not ok:
            all_critical_pass = False

    print()
    if all_critical_pass:
        print("✓ All critical services are running. Damascus is ready!")
        print("\nNext steps:")
        print("  cd backend && poetry run uvicorn damascus.main:app --reload")
        print("  damascus config health")
        print("  damascus workspace create 'My First Workspace'")
    else:
        print("✗ Some critical services are not running.")
        print("  Start infrastructure with: docker compose up -d")
        print("  Then start the backend:    cd backend && poetry run uvicorn damascus.main:app --reload")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
