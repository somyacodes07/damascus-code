"""
Workflow CLI commands
======================
Implements: damascus workflow [list|run]
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from damascus_cli.client import DamascusClient, run_async

app = typer.Typer(help="Manage and run workflows.")
console = Console()


@app.command("list")
def list_workflows(workspace_id: str = typer.Argument(..., help="Workspace ID")):
    """List workflows in a workspace."""
    async def _run():
        async with DamascusClient() as client:
            result = await client.list_workflows(workspace_id)
        items = result.get("data", [])
        if not items:
            console.print("[dim]No workflows found.[/dim]")
            return
        table = Table(title="Workflows", header_style="bold blue")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("Version")
        for wf in items:
            table.add_row(wf["id"], wf["name"], wf["status"], str(wf.get("version", 1)))
        console.print(table)
    run_async(_run())


@app.command("run")
def run_workflow(
    workflow_id: str = typer.Argument(..., help="Workflow ID"),
    input_json: Optional[str] = typer.Option(None, "--input", "-i", help="JSON inputs string"),
):
    """Execute a workflow."""
    inputs = {}
    if input_json:
        try:
            inputs = json.loads(input_json)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON input: {e}[/red]")
            raise typer.Exit(1)

    async def _run():
        async with DamascusClient() as client:
            result = await client.execute_workflow(workflow_id, inputs)
        data = result.get("data", {})
        console.print(f"[green]✓[/green] Started execution [bold]{data.get('execution_id')}[/bold]")
        console.print(f"  Status: {data.get('status')}")
    run_async(_run())
