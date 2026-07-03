"""
Model CLI commands
===================
Implements: damascus model [list|generate]
"""

from __future__ import annotations

import typer
from rich.console import Console

from damascus_cli.client import DamascusClient, run_async
from damascus_cli.output.console import success, error, print_key_value, print_table

app = typer.Typer(help="Manage and use AI model providers.")
console = Console()


@app.command("list")
def list_models():
    """List all available models grouped by provider."""
    async def _run():
        async with DamascusClient() as client:
            result = await client.list_models()
        data = result.get("data", {})
        if not data:
            console.print("[dim]No model providers available. Is Ollama running?[/dim]")
            return
        for provider, models in data.items():
            console.print(f"\n[bold cyan]{provider}[/bold cyan]")
            if models:
                for model in models:
                    console.print(f"  • {model}")
            else:
                console.print("  [dim](no models loaded)[/dim]")
    run_async(_run())


@app.command("health")
def provider_health():
    """Check which model providers are reachable."""
    async def _run():
        async with DamascusClient() as client:
            resp = await client._client.get("/api/v1/models/health")
            resp.raise_for_status()
            data = resp.json()["data"]
        for provider, available in data.items():
            if available:
                console.print(f"  [green]✓[/green]  {provider}")
            else:
                console.print(f"  [red]✗[/red]  {provider} [dim](unavailable)[/dim]")
    run_async(_run())


@app.command("generate")
def generate(
    prompt: str = typer.Argument(..., help="The prompt to send to the model"),
    model: str = typer.Option("", "--model", "-m", help="Model name (e.g., llama3.1)"),
    system: str = typer.Option("", "--system", "-s", help="System prompt"),
    temperature: float = typer.Option(0.7, "--temperature", "-t"),
):
    """Send a prompt to the default model provider and print the response."""
    async def _run():
        async with DamascusClient() as client:
            resp = await client._client.post(
                "/api/v1/models/generate",
                json={
                    "prompt": prompt,
                    "model": model,
                    "system_prompt": system,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()["data"]

        console.print(f"\n[bold]Response[/bold] [dim]({data['provider']}/{data['model']})[/dim]:\n")
        console.print(data["content"])
        usage = data.get("usage", {})
        console.print(f"\n[dim]Tokens: {usage.get('total_tokens', 0)} total[/dim]")
    run_async(_run())
