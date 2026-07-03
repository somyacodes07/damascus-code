"""
Database Connection — PostgreSQL via SQLAlchemy async
=====================================================
Provides async engine, session factory, and base model.
Used by all subsystems for structured data storage and episodic memory.

Credentials: DAMASCUS_DATABASE_URL (see config.py)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from damascus.config import settings

# ---------------------------------------------------------------------------
# Naming convention for alembic migrations (auto-names constraints)
# ---------------------------------------------------------------------------
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    Import and extend this in every subsystem's models.py.
    """
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ---------------------------------------------------------------------------
# Engine (module-level singleton — created once at startup)
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the shared async engine, creating it if needed."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database.url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=settings.database.pool_pre_ping,
            echo=settings.is_development,  # Log SQL in development only
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory, creating it if needed."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    Usage:
        @router.get("/")
        async def handler(session: AsyncSession = Depends(get_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_engine() -> None:
    """Dispose of the engine connection pool. Call on application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
