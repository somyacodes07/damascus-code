"""
Observability — OpenTelemetry + Prometheus Integration
=======================================================
Every execution must be observable.
This module sets up tracing (OpenTelemetry), metrics (Prometheus),
and structured logging (structlog).

Key metrics:
- workflow_executions_total
- workflow_duration_seconds
- node_executions_total
- agent_invocations_total
- model_tokens_used_total
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from prometheus_client import Counter, Histogram, make_asgi_app

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

workflow_executions_total = Counter(
    "damascus_workflow_executions_total",
    "Total number of workflow executions started",
    ["workspace_id", "status"],
)

workflow_duration_seconds = Histogram(
    "damascus_workflow_duration_seconds",
    "Duration of workflow executions in seconds",
    ["workspace_id"],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600],
)

node_executions_total = Counter(
    "damascus_node_executions_total",
    "Total number of workflow node executions",
    ["node_type", "status"],
)

agent_invocations_total = Counter(
    "damascus_agent_invocations_total",
    "Total number of agent invocations",
    ["agent_id"],
)

model_tokens_used_total = Counter(
    "damascus_model_tokens_used_total",
    "Total tokens consumed from model providers",
    ["provider", "model"],
)

# ---------------------------------------------------------------------------
# Structured logging setup
# ---------------------------------------------------------------------------


def configure_logging(log_level: str = "info") -> None:
    """
    Configure structlog for structured JSON logging in production,
    and human-readable console logging in development.
    """
    import logging
    import sys

    from damascus.config import settings

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class ExecutionTimer:
    """Context manager for timing workflow/node executions."""

    def __init__(self, workspace_id: str) -> None:
        self._workspace_id = workspace_id
        self._start = 0.0

    def __enter__(self) -> ExecutionTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        duration = time.perf_counter() - self._start
        workflow_duration_seconds.labels(workspace_id=self._workspace_id).observe(duration)


# Expose Prometheus metrics as ASGI middleware
metrics_app = make_asgi_app()
