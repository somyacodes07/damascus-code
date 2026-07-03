"""
Console Output Formatting
===========================
Centralized output helpers for consistent CLI formatting.
All CLI commands use these helpers for a uniform look and feel.

Uses Rich for colored terminal output with consistent styles.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich import box

# Shared console — always writes to stdout
console = Console()

# Error console — writes to stderr so it can be distinguished from normal output
error_console = Console(stderr=True, style="bold red")


# ---------------------------------------------------------------------------
# Status messages
# ---------------------------------------------------------------------------

def success(message: str) -> None:
    """Print a success message with a green checkmark."""
    console.print(f"[green]✓[/green]  {message}")


def error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[bold red]✗[/bold red]  {message}")


def warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow]  {message}")


def info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[dim]ℹ[/dim]  {message}")


def heading(title: str) -> None:
    """Print a section heading."""
    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    console.print("[dim]" + "─" * len(title) + "[/dim]")


# ---------------------------------------------------------------------------
# Data output
# ---------------------------------------------------------------------------

def print_table(
    rows: list[dict[str, Any]],
    columns: list[str],
    title: str = "",
    styles: dict[str, str] | None = None,
) -> None:
    """Print data as a Rich table."""
    table = Table(title=title, box=box.ROUNDED, show_header=True, header_style="bold blue")
    for col in columns:
        style = (styles or {}).get(col, "")
        table.add_column(col, style=style)
    for row in rows:
        table.add_row(*[str(row.get(col, "")) for col in columns])
    console.print(table)


def print_json(data: Any) -> None:
    """Print data as pretty-printed JSON."""
    import json
    json_str = json.dumps(data, indent=2, default=str)
    console.print(Syntax(json_str, "json", theme="monokai", word_wrap=True))


def print_panel(content: str, title: str = "", style: str = "blue") -> None:
    """Print content inside a Rich panel box."""
    console.print(Panel(content, title=title, border_style=style))


def print_key_value(data: dict[str, Any], title: str = "") -> None:
    """Print key-value pairs in a clean format."""
    if title:
        heading(title)
    max_key_len = max((len(k) for k in data.keys()), default=10)
    for key, value in data.items():
        padded = key.ljust(max_key_len + 2)
        console.print(f"  [dim]{padded}[/dim] {value}")


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------

def print_pagination(pagination: dict[str, Any]) -> None:
    """Print pagination info."""
    total = pagination.get("total", 0)
    page = pagination.get("page", 1)
    total_pages = pagination.get("total_pages", 1)
    per_page = pagination.get("per_page", 20)
    console.print(
        f"[dim]Showing page {page}/{total_pages} — {total} total (up to {per_page} per page)[/dim]"
    )
