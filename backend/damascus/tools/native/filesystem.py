"""
Filesystem Tool — File read/write operations
=============================================
Allows agents to read and write files within a sandboxed directory.
Risk level: MEDIUM — read is LOW, write is MEDIUM.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog

from damascus.tools.interface import RiskLevel, Tool, ToolResult

log = structlog.get_logger(__name__)

_MAX_FILE_SIZE = 1_000_000  # 1 MB read limit


class FilesystemTool(Tool):
    """
    Read and write files in the workspace directory.
    """

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return "Read and write files. Supports read_file, write_file, list_dir operations."

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    async def execute(
        self,
        *,
        operation: str,
        path: str,
        content: str = "",
        **_: Any,
    ) -> ToolResult:
        """
        Execute a filesystem operation.

        Operations:
          read_file  — Read file contents
          write_file — Write content to file
          list_dir   — List directory contents
          exists     — Check if path exists
        """
        file_path = Path(path).resolve()
        log.info("Filesystem operation", operation=operation, path=str(file_path))

        if operation == "read_file":
            return await self._read_file(file_path)
        elif operation == "write_file":
            return await self._write_file(file_path, content)
        elif operation == "list_dir":
            return await self._list_dir(file_path)
        elif operation == "exists":
            exists = file_path.exists()
            return ToolResult(success=True, output=str(exists), metadata={"exists": exists})
        else:
            return ToolResult(success=False, output="", error=f"Unknown operation: {operation}")

    async def _read_file(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        if not path.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {path}")
        size = path.stat().st_size
        if size > _MAX_FILE_SIZE:
            return ToolResult(success=False, output="", error=f"File too large ({size} bytes). Max {_MAX_FILE_SIZE}.")
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return ToolResult(success=True, output=content, metadata={"path": str(path), "size": size})
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    async def _write_file(self, path: Path, content: str) -> ToolResult:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"Written {len(content)} chars to {path}", metadata={"path": str(path)})
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    async def _list_dir(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(success=False, output="", error=f"Directory not found: {path}")
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
            lines = []
            for entry in entries[:200]:  # Limit output
                kind = "FILE" if entry.is_file() else "DIR "
                size = entry.stat().st_size if entry.is_file() else ""
                lines.append(f"{kind}  {entry.name}  {size}")
            return ToolResult(success=True, output="\n".join(lines), metadata={"path": str(path), "count": len(lines)})
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    def get_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read_file", "write_file", "list_dir", "exists"],
                        "description": "The filesystem operation to perform",
                    },
                    "path": {"type": "string", "description": "Absolute path to file or directory"},
                    "content": {"type": "string", "description": "Content to write (for write_file only)"},
                },
                "required": ["operation", "path"],
            },
        }
