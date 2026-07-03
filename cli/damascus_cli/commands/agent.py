"""
Agent CLI commands
===================
Implements: damascus agent [list|create|get]
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from damascus_cli.client import DamascusClient, run_async
from damascus_cli.output.console import print_table, success, error, print_key_value

app = typer.Typer(help="Manage agent profiles.")
console = Console()


@app.command("list")
def list_agents(workspace_id: str = typer.Argument(..., help="Workspace ID")):
    """List agent profiles in a workspace."""
    async def _run():
        async with DamascusClient() as client:
            resp = await client._client.get("/api/v1/agents", params={"workspace_id": workspace_id})
            resp.raise_for_status()
            result = resp.json()
        items = result.get("data", [])
        if not items:
            console.print("[dim]No agent profiles found.[/dim]")
            return
        print_table(
            rows=items,
            columns=["id", "name", "model_preference", "status"],
            title="Agent Profiles",
        )
    run_async(_run())


@app.command("get")
def get_agent(agent_id: str = typer.Argument(..., help="Agent ID")):
    """Show details of an agent profile."""
    async def _run():
        async with DamascusClient() as client:
            resp = await client._client.get(f"/api/v1/agents/{agent_id}")
            resp.raise_for_status()
            agent = resp.json()["data"]
        print_key_value({
            "ID": agent["id"],
            "Name": agent["name"],
            "Description": agent.get("description", ""),
            "Model": agent.get("model_preference", ""),
            "Capabilities": ", ".join(agent.get("capabilities", [])),
            "Tools": ", ".join(agent.get("tools", [])),
            "Max Iterations": str(agent.get("max_iterations", 10)),
            "Temperature": str(agent.get("temperature", 0.7)),
            "Status": agent.get("status", ""),
        }, title=agent["name"])
    run_async(_run())
