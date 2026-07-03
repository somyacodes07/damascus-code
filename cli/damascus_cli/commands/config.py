"""
Config CLI commands
====================
Implements: damascus config [show|health]
"""

from __future__ import annotations

import os

import typer
from rich.console import Console
from rich.table import Table

from damascus_cli.client import DamascusClient, run_async

app = typer.Typer(help="Configuration and system status.")
console = Console()


@app.command("health")
def health():
    """Check the health of all Damascus services."""
    async def _run():
        async with DamascusClient() as client:
            data = await client.health()
        status = data.get("status", "unknown")
        color = "green" if status == "healthy" else "yellow" if status == "degraded" else "red"
        console.print(f"\n[bold {color}]Damascus: {status.upper()}[/bold {color}]")
        console.print(f"  Version:  {data.get('version', '?')}")
        console.print(f"  Uptime:   {data.get('uptime_seconds', 0)}s")
        console.print(f"  Env:      {data.get('environment', '?')}")
        console.print()

        services = data.get("services", {})
        if services:
            table = Table(title="Services", header_style="bold")
            table.add_column("Service")
            table.add_column("Status")
            for name, svc_status in services.items():
                if isinstance(svc_status, dict):
                    # Model provider dict
                    for provider, ok in svc_status.items():
                        icon = "✓" if ok else "✗"
                        color_str = "green" if ok else "red"
                        table.add_row(f"{name}/{provider}", f"[{color_str}]{icon}[/{color_str}]")
                else:
                    icon = "✓" if svc_status == "healthy" else "✗"
                    color_str = "green" if svc_status == "healthy" else "red"
                    table.add_row(name, f"[{color_str}]{icon} {svc_status}[/{color_str}]")
            console.print(table)
    run_async(_run())


@app.command("show")
def show_config():
    """Show the current CLI configuration."""
    api_url = os.getenv("DAMASCUS_API_URL", "http://localhost:8000")
    console.print("[bold]Damascus CLI Configuration[/bold]")
    console.print(f"  API URL:  {api_url}")
    console.print("  Version:  0.1.0")
