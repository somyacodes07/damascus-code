"""
Workspace CLI commands
=======================
Implements: damascus workspace [list|create|get|delete]
"""

from __future__ import annotations


import typer
from rich.console import Console
from rich.table import Table

from damascus_cli.client import DamascusClient, run_async

app = typer.Typer(help="Manage workspaces.")
console = Console()


@app.command("list")
def list_workspaces():
    """List all your workspaces."""
    async def _run():
        async with DamascusClient() as client:
            data = await client.list_workspaces()
        items = data.get("data", [])
        if not items:
            console.print("[dim]No workspaces found. Create one with: damascus workspace create[/dim]")
            return
        table = Table(title="Workspaces", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("Created")
        for ws in items:
            table.add_row(ws["id"], ws["name"], ws["status"], ws.get("created_at", "")[:10])
        console.print(table)
    run_async(_run())


@app.command("create")
def create_workspace(
    name: str = typer.Argument(..., help="Workspace name"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
):
    """Create a new workspace."""
    async def _run():
        async with DamascusClient() as client:
            result = await client.create_workspace(name, description)
        ws = result["data"]
        console.print(f"[green]✓[/green] Created workspace [bold]{ws['name']}[/bold] (ID: {ws['id']})")
    run_async(_run())


@app.command("get")
def get_workspace(workspace_id: str = typer.Argument(..., help="Workspace ID")):
    """Show details of a workspace."""
    async def _run():
        async with DamascusClient() as client:
            result = await client.get_workspace(workspace_id)
        ws = result["data"]
        console.print(f"[bold]{ws['name']}[/bold]")
        console.print(f"  ID:          {ws['id']}")
        console.print(f"  Description: {ws.get('description', '')}")
        console.print(f"  Status:      {ws['status']}")
        console.print(f"  Created:     {ws.get('created_at', '')[:19]}")
    run_async(_run())


@app.command("delete")
def delete_workspace(
    workspace_id: str = typer.Argument(..., help="Workspace ID"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a workspace (soft delete)."""
    if not confirm:
        typer.confirm(f"Delete workspace {workspace_id}?", abort=True)

    async def _run():
        async with DamascusClient() as client:
            await client.delete_workspace(workspace_id)
        console.print(f"[yellow]Deleted workspace {workspace_id}[/yellow]")
    run_async(_run())
