"""
Memory CLI commands
====================
Implements: damascus memory [search|list]
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from damascus_cli.client import DamascusClient, run_async

app = typer.Typer(help="Browse and search memories.")
console = Console()


@app.command("search")
def search_memories(
    workspace_id: str = typer.Argument(..., help="Workspace ID"),
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n"),
):
    """Search memories by semantic similarity."""
    async def _run():
        async with DamascusClient() as client:
            result = await client.search_memories(workspace_id, query, limit)
        items = result.get("data", [])
        if not items:
            console.print("[dim]No matching memories found.[/dim]")
            return
        table = Table(title=f"Memory Search: '{query}'", show_header=True, header_style="bold magenta")
        table.add_column("Score", width=8)
        table.add_column("Summary")
        table.add_column("Tags")
        for m in items:
            score = f"{m.get('score', 0):.3f}"
            summary = (m.get("summary") or m.get("content", ""))[:80]
            tags = ", ".join(m.get("tags", []))
            table.add_row(score, summary, tags)
        console.print(table)
    run_async(_run())


@app.command("list")
def list_memories(
    workspace_id: str = typer.Argument(..., help="Workspace ID"),
    page: int = typer.Option(1, "--page", "-p"),
):
    """List all memories in a workspace."""
    async def _run():
        async with DamascusClient() as client:
            result = await client.list_memories(workspace_id, page=page)
        items = result.get("data", [])
        pagination = result.get("pagination", {})
        if not items:
            console.print("[dim]No memories found.[/dim]")
            return
        table = Table(title=f"Memories (page {page}/{pagination.get('total_pages', 1)})")
        table.add_column("ID", style="dim")
        table.add_column("Type")
        table.add_column("Summary")
        table.add_column("Importance")
        for m in items:
            summary = (m.get("summary") or m.get("content", ""))[:60]
            table.add_row(m["id"], m.get("type", ""), summary, f"{m.get('importance', 0):.1f}")
        console.print(table)
        console.print(f"[dim]Total: {pagination.get('total', 0)} memories[/dim]")
    run_async(_run())
