"""
Terminal Tool — Native shell command execution
===============================================
Allows agents to execute shell commands in a sandboxed environment.
Risk level: HIGH — requires human approval by default.

Security constraints:
- Command execution is sandboxed in development (subprocess with timeout)
- Full sandbox policy (containerized) is enforced in production
- Commands are logged for audit trail
- Timeout enforced to prevent runaway processes
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from damascus.tools.interface import RiskLevel, Tool, ToolResult

log = structlog.get_logger(__name__)

_DEFAULT_TIMEOUT = 30  # seconds
_MAX_OUTPUT_LENGTH = 10_000  # characters


class TerminalTool(Tool):
    """
    Execute shell commands.
    HIGH risk — requires approval by default.
    """

    @property
    def name(self) -> str:
        return "terminal"

    @property
    def description(self) -> str:
        return "Execute shell commands and return their stdout/stderr output."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH

    async def execute(
        self, *, command: str, timeout: int = _DEFAULT_TIMEOUT, **_: Any
    ) -> ToolResult:
        """Execute a shell command asynchronously with a timeout."""
        log.info("Executing terminal command", command=command[:200])

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            output_str = stdout.decode(errors="replace")
            error_str = stderr.decode(errors="replace")

            # Truncate to prevent massive outputs
            if len(output_str) > _MAX_OUTPUT_LENGTH:
                output_str = output_str[:_MAX_OUTPUT_LENGTH] + "\n[Output truncated]"

            combined = output_str
            if error_str:
                combined += f"\n[stderr]\n{error_str[:2000]}"

            success = proc.returncode == 0
            log.info("Terminal command completed", return_code=proc.returncode)

            return ToolResult(
                success=success,
                output=combined,
                error=error_str if not success else None,
                metadata={"return_code": proc.returncode, "command": command},
            )

        except TimeoutError:
            log.warning("Terminal command timed out", command=command[:200], timeout=timeout)
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds.",
                metadata={"command": command, "timeout": timeout},
            )
        except Exception as exc:
            log.error("Terminal command failed", error=str(exc))
            return ToolResult(
                success=False,
                output="",
                error=str(exc),
                metadata={"command": command},
            )

    def get_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": _DEFAULT_TIMEOUT,
                    },
                },
                "required": ["command"],
            },
        }
