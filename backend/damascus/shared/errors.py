"""
Common Error Types
==================
Shared exception hierarchy for the Damascus platform.
All subsystems raise from these base classes.

Design rules:
- Every exception must have a machine-readable `code` attribute
- Codes follow UPPER_SNAKE_CASE (e.g., WORKSPACE_NOT_FOUND)
- HTTP status codes are only mapped at the API layer, not here
"""

from __future__ import annotations


class DamascusError(Exception):
    """
    Base exception for all Damascus errors.
    Every subclass must provide a `code` class attribute.
    """

    code: str = "DAMASCUS_ERROR"
    message: str = "An internal Damascus error occurred."

    def __init__(self, message: str | None = None, **details: object) -> None:
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# Not Found Errors
# ---------------------------------------------------------------------------


class NotFoundError(DamascusError):
    code = "NOT_FOUND"
    message = "The requested resource was not found."


class WorkspaceNotFoundError(NotFoundError):
    code = "WORKSPACE_NOT_FOUND"
    message = "The workspace was not found."


class WorkflowNotFoundError(NotFoundError):
    code = "WORKFLOW_NOT_FOUND"
    message = "The workflow was not found."


class AgentNotFoundError(NotFoundError):
    code = "AGENT_NOT_FOUND"
    message = "The agent profile was not found."


class MemoryNotFoundError(NotFoundError):
    code = "MEMORY_NOT_FOUND"
    message = "The memory record was not found."


class ExecutionNotFoundError(NotFoundError):
    code = "EXECUTION_NOT_FOUND"
    message = "The workflow execution was not found."


# ---------------------------------------------------------------------------
# Conflict Errors
# ---------------------------------------------------------------------------


class ConflictError(DamascusError):
    code = "CONFLICT"
    message = "A resource with this identifier already exists."


class WorkspaceAlreadyExistsError(ConflictError):
    code = "WORKSPACE_ALREADY_EXISTS"
    message = "A workspace with this name already exists."


class WorkflowAlreadyExistsError(ConflictError):
    code = "WORKFLOW_ALREADY_EXISTS"
    message = "A workflow with this name already exists in this workspace."


# ---------------------------------------------------------------------------
# Validation Errors
# ---------------------------------------------------------------------------


class ValidationError(DamascusError):
    code = "VALIDATION_ERROR"
    message = "The provided data failed validation."


class InvalidWorkflowDefinitionError(ValidationError):
    code = "INVALID_WORKFLOW_DEFINITION"
    message = "The workflow definition is invalid."


# ---------------------------------------------------------------------------
# Authorization Errors
# ---------------------------------------------------------------------------


class AuthorizationError(DamascusError):
    code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action."


class ApprovalRequiredError(DamascusError):
    code = "APPROVAL_REQUIRED"
    message = "This action requires human approval before proceeding."


# ---------------------------------------------------------------------------
# Infrastructure Errors
# ---------------------------------------------------------------------------


class InfrastructureError(DamascusError):
    code = "INFRASTRUCTURE_ERROR"
    message = "An infrastructure service is unavailable."


class DatabaseError(InfrastructureError):
    code = "DATABASE_ERROR"
    message = "A database error occurred."


class CacheError(InfrastructureError):
    code = "CACHE_ERROR"
    message = "A cache (Redis) error occurred."


class MessagingError(InfrastructureError):
    code = "MESSAGING_ERROR"
    message = "A messaging (NATS) error occurred."


class VectorStoreError(InfrastructureError):
    code = "VECTOR_STORE_ERROR"
    message = "A vector store (Qdrant) error occurred."


# ---------------------------------------------------------------------------
# Model Provider Errors
# ---------------------------------------------------------------------------


class ModelProviderError(DamascusError):
    code = "MODEL_PROVIDER_ERROR"
    message = "A model provider error occurred."


class ModelProviderUnavailableError(ModelProviderError):
    code = "MODEL_PROVIDER_UNAVAILABLE"
    message = "The model provider is currently unavailable."


class NoModelProviderConfiguredError(ModelProviderError):
    code = "NO_MODEL_PROVIDER_CONFIGURED"
    message = "No model provider is configured. Add at least one provider."


# ---------------------------------------------------------------------------
# Execution Errors
# ---------------------------------------------------------------------------


class ExecutionError(DamascusError):
    code = "EXECUTION_ERROR"
    message = "Workflow execution failed."


class WorkflowAlreadyRunningError(ExecutionError):
    code = "WORKFLOW_ALREADY_RUNNING"
    message = "The workflow is already running and cannot be started again."


class WorkflowNotRunningError(ExecutionError):
    code = "WORKFLOW_NOT_RUNNING"
    message = "The workflow is not currently running."


# ---------------------------------------------------------------------------
# Team Errors (Phase 2 — Milestone 2.1)
# ---------------------------------------------------------------------------


class TeamNotFoundError(NotFoundError):
    code = "TEAM_NOT_FOUND"
    message = "The team was not found."


# ---------------------------------------------------------------------------
# Agent Communication Errors (Phase 2 — Milestone 2.1)
# ---------------------------------------------------------------------------


class MessageBudgetExceededError(DamascusError):
    code = "MESSAGE_BUDGET_EXCEEDED"
    message = "The inter-agent message budget has been exhausted."


class MessageTooLargeError(DamascusError):
    code = "MESSAGE_TOO_LARGE"
    message = "The agent message payload exceeds the maximum allowed size."


# ---------------------------------------------------------------------------
# Model Routing Errors (Phase 2 — Milestone 2.2)
# ---------------------------------------------------------------------------


class RoutingError(DamascusError):
    code = "ROUTING_ERROR"
    message = "Model routing failed."


class NoEligibleModelError(RoutingError):
    code = "NO_ELIGIBLE_MODEL"
    message = "No model satisfies the requested capability and policy constraints."


# ---------------------------------------------------------------------------
# MCP Errors (Phase 2 — Milestone 2.3)
# ---------------------------------------------------------------------------


class MCPError(DamascusError):
    code = "MCP_ERROR"
    message = "An MCP protocol error occurred."


class MCPServerError(MCPError):
    code = "MCP_SERVER_ERROR"
    message = "The MCP server is unavailable or returned an error."


class MCPToolNotFoundError(MCPError):
    code = "MCP_TOOL_NOT_FOUND"
    message = "The requested MCP tool was not found."


# ---------------------------------------------------------------------------
# Benchmark Errors (Phase 2 — Milestone 2.4)
# ---------------------------------------------------------------------------


class BenchmarkNotFoundError(NotFoundError):
    code = "BENCHMARK_NOT_FOUND"
    message = "The benchmark was not found."


class BenchmarkRunFailedError(ExecutionError):
    code = "BENCHMARK_RUN_FAILED"
    message = "The benchmark run failed during execution."


# ---------------------------------------------------------------------------
# Evolution Errors (Phase 2 — Milestone 2.5)
# ---------------------------------------------------------------------------


class ExperimentNotFoundError(NotFoundError):
    code = "EXPERIMENT_NOT_FOUND"
    message = "The experiment was not found."


class ExperimentAlreadyRunningError(ConflictError):
    code = "EXPERIMENT_ALREADY_RUNNING"
    message = "An experiment is already running for this target."


class PromotionNotFoundError(NotFoundError):
    code = "PROMOTION_NOT_FOUND"
    message = "The promotion record was not found."


class RollbackFailedError(ExecutionError):
    code = "ROLLBACK_FAILED"
    message = "The rollback operation failed."


class SafetyConstraintViolationError(DamascusError):
    code = "SAFETY_CONSTRAINT_VIOLATION"
    message = "The variant violates an immutable safety constraint."


# ---------------------------------------------------------------------------
# Research Errors (Phase 2 — Milestone 2.6)
# ---------------------------------------------------------------------------


class ResearchTaskNotFoundError(NotFoundError):
    code = "RESEARCH_TASK_NOT_FOUND"
    message = "The research task was not found."
