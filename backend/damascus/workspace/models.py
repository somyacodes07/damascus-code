"""
Workspace System — ORM Models
==============================
Defines the SQLAlchemy ORM models for the Workspace domain:
- Workspace
- Project
- WorkflowDefinition
- WorkflowExecution
- WorkflowNode

Following the data model spec in docs/03-Implementation/Data-Models.md
ID format: ws_abc123, proj_abc123, wf_abc123, exec_abc123, node_abc123
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from damascus.shared.database import Base

# ---------------------------------------------------------------------------
# Enums (stored as strings in DB)
# ---------------------------------------------------------------------------

class WorkspaceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class ProjectStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class WorkflowStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeType(str, Enum):
    AGENT = "AGENT"
    TOOL = "TOOL"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    MODEL = "MODEL"
    BENCHMARK = "BENCHMARK"
    CONDITIONAL = "CONDITIONAL"
    PARALLEL = "PARALLEL"


# ---------------------------------------------------------------------------
# Helper to generate Damascus-prefixed IDs
# ---------------------------------------------------------------------------

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class Workspace(Base):
    """
    The top-level organizational boundary.
    Everything in Damascus belongs to a workspace.
    """
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _new_id("ws"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=WorkspaceStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    projects: Mapped[list[Project]] = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")
    workflow_definitions: Mapped[list[WorkflowDefinition]] = relationship(
        "WorkflowDefinition", back_populates="workspace", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_workspace_owner_name"),
    )


class Project(Base):
    """
    A project groups related workflows within a workspace.
    """
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _new_id("proj"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default=ProjectStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="projects")


class WorkflowDefinition(Base):
    """
    Blueprint for workflow execution.
    Versioned — each update increments the version number.
    """
    __tablename__ = "workflow_definitions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _new_id("wf"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nodes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    edges: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=WorkflowStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="workflow_definitions")
    executions: Mapped[list[WorkflowExecution]] = relationship(
        "WorkflowExecution", back_populates="workflow_definition", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_workflow_workspace_name"),
    )


class WorkflowExecution(Base):
    """
    A running (or completed) instance of a WorkflowDefinition.
    """
    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _new_id("exec"))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=ExecutionStatus.PENDING)
    initiated_by: Mapped[str] = mapped_column(String(64), default="user")
    checkpoint_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workflow_definition: Mapped[WorkflowDefinition] = relationship(
        "WorkflowDefinition", back_populates="executions"
    )
