"""
Initial Schema — Damascus V1
==============================
Creates all database tables for Phase 1.

Tables created:
  - workspaces
  - projects
  - workflow_definitions
  - workflow_executions
  - agent_profiles
  - agent_performance
  - memory_records
  - memory_links

Revision ID: 001
Revises: (none — initial migration)
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # workspaces
    # ----------------------------------------------------------------
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("settings", postgresql.JSONB, default={}),
        sa.Column("status", sa.String(32), default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])
    op.create_index("ix_workspaces_status", "workspaces", ["status"])

    # ----------------------------------------------------------------
    # projects
    # ----------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(32),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("tags", postgresql.JSONB, default=[]),
        sa.Column("status", sa.String(32), default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])

    # ----------------------------------------------------------------
    # workflow_definitions
    # ----------------------------------------------------------------
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(32),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("nodes", postgresql.JSONB, default=[]),
        sa.Column("edges", postgresql.JSONB, default=[]),
        sa.Column("input_schema", postgresql.JSONB, default={}),
        sa.Column("output_schema", postgresql.JSONB, default={}),
        sa.Column("created_by", sa.String(255), default=""),
        sa.Column("status", sa.String(32), default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_definitions_workspace_id", "workflow_definitions", ["workspace_id"]
    )
    op.create_index("ix_workflow_definitions_status", "workflow_definitions", ["status"])

    # ----------------------------------------------------------------
    # workflow_executions
    # ----------------------------------------------------------------
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.String(32),
            sa.ForeignKey("workflow_definitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("workspace_id", sa.String(32), nullable=False),
        sa.Column("inputs", postgresql.JSONB, default={}),
        sa.Column("outputs", postgresql.JSONB, default={}),
        sa.Column("state", postgresql.JSONB, default={}),
        sa.Column("status", sa.String(32), default="PENDING"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("checkpoint_id", sa.String(255), nullable=True),
        sa.Column("initiated_by", sa.String(255), default=""),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_executions_workspace_id", "workflow_executions", ["workspace_id"])
    op.create_index("ix_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"])
    op.create_index("ix_workflow_executions_status", "workflow_executions", ["status"])

    # ----------------------------------------------------------------
    # agent_profiles
    # ----------------------------------------------------------------
    op.create_table(
        "agent_profiles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("capabilities", postgresql.JSONB, default=[]),
        sa.Column("model_preference", sa.String(255), default="ollama/llama3.1"),
        sa.Column("tools", postgresql.JSONB, default=[]),
        sa.Column("max_iterations", sa.Integer, default=10),
        sa.Column("temperature", sa.Float, default=0.7),
        sa.Column("status", sa.String(32), default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_profiles_workspace_id", "agent_profiles", ["workspace_id"])

    # ----------------------------------------------------------------
    # agent_performance
    # ----------------------------------------------------------------
    op.create_table(
        "agent_performance",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "agent_profile_id",
            sa.String(32),
            sa.ForeignKey("agent_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("execution_id", sa.String(32), nullable=False),
        sa.Column("task_type", sa.String(128), default=""),
        sa.Column("success", sa.Boolean, default=True),
        sa.Column("quality_score", sa.Float, default=0.0),
        sa.Column("latency_ms", sa.Integer, default=0),
        sa.Column("token_usage", sa.Integer, default=0),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agent_performance_agent_profile_id", "agent_performance", ["agent_profile_id"]
    )

    # ----------------------------------------------------------------
    # memory_records
    # ----------------------------------------------------------------
    op.create_table(
        "memory_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.String(32), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, default=""),
        sa.Column("source_type", sa.String(32), default="WORKFLOW"),
        sa.Column("source_id", sa.String(255), default=""),
        sa.Column("tags", postgresql.JSONB, default=[]),
        sa.Column("importance", sa.Float, default=0.5),
        sa.Column("confidence", sa.Float, default=1.0),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("access_count", sa.Integer, default=0),
        sa.Column("status", sa.String(32), default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_memory_records_workspace_id", "memory_records", ["workspace_id"])
    op.create_index("ix_memory_records_type", "memory_records", ["type"])
    op.create_index("ix_memory_records_status", "memory_records", ["status"])

    # ----------------------------------------------------------------
    # memory_links
    # ----------------------------------------------------------------
    op.create_table(
        "memory_links",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "source_memory_id",
            sa.String(32),
            sa.ForeignKey("memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_memory_id",
            sa.String(32),
            sa.ForeignKey("memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship", sa.String(64), nullable=False),
        sa.Column("strength", sa.Float, default=1.0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_memory_links_source", "memory_links", ["source_memory_id"])
    op.create_index("ix_memory_links_target", "memory_links", ["target_memory_id"])


def downgrade() -> None:
    op.drop_table("memory_links")
    op.drop_table("memory_records")
    op.drop_table("agent_performance")
    op.drop_table("agent_profiles")
    op.drop_table("workflow_executions")
    op.drop_table("workflow_definitions")
    op.drop_table("projects")
    op.drop_table("workspaces")
