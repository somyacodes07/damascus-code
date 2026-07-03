"""
Memory — ORM Models
====================
Defines the SQLAlchemy models for the Memory domain:
- MemoryRecord
- MemoryLink

Memory types (from docs):
  EPISODIC  — completed workflow records (PostgreSQL)
  SEMANTIC  — vector similarity (Qdrant, referenced by embedding_id)
  PROCEDURAL — learned strategies (Phase 3)
  EVOLUTION  — evolution insights (Phase 2)

All memory records live in PostgreSQL for authoritative storage.
Qdrant holds the vector embeddings referenced by embedding_id.
Redis holds working memory (active execution state — not modeled here).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from damascus.shared.database import Base


class MemoryType(str, Enum):
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    PROCEDURAL = "PROCEDURAL"
    EVOLUTION = "EVOLUTION"


class MemorySource(str, Enum):
    WORKFLOW = "WORKFLOW"
    USER = "USER"
    RESEARCH = "RESEARCH"
    EVOLUTION = "EVOLUTION"


class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DEPRECATED = "DEPRECATED"


class RelationshipType(str, Enum):
    DERIVED_FROM = "DERIVED_FROM"
    RELATED_TO = "RELATED_TO"
    IMPROVED_BY = "IMPROVED_BY"
    CONTRADICTS = "CONTRADICTS"
    SUPPORTS = "SUPPORTS"


def _new_mem_id() -> str:
    return f"mem_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryRecord(Base):
    """
    A single piece of stored memory.
    Source of truth is PostgreSQL; vectors live in Qdrant.
    """
    __tablename__ = "memory_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_mem_id)
    workspace_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), default="")
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    embedding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=MemoryStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    # Links to other memories (knowledge graph edges)
    outgoing_links: Mapped[list["MemoryLink"]] = orm_relationship(
        "MemoryLink", foreign_keys="MemoryLink.source_memory_id", back_populates="source_memory",
        cascade="all, delete-orphan",
    )


class MemoryLink(Base):
    """
    Connects two memory records.
    Used to build the knowledge graph (Phase 3 full graph via Apache AGE).
    In Phase 1, stored directly in PostgreSQL.
    """
    __tablename__ = "memory_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"link_{uuid.uuid4().hex[:12]}")
    source_memory_id: Mapped[str] = mapped_column(ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False)
    target_memory_id: Mapped[str] = mapped_column(String(32), nullable=False)
    relationship: Mapped[str] = mapped_column(String(32), nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    source_memory: Mapped["MemoryRecord"] = orm_relationship(
        "MemoryRecord", foreign_keys="MemoryLink.source_memory_id", back_populates="outgoing_links"
    )
