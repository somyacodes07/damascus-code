"""
Damascus CLI — Entry Point
============================
The main `damascus` command.

Usage:
  damascus --help
  damascus workspace list
  damascus workflow run <id>
  damascus memory search <workspace_id> <query>
  damascus agent list <workspace_id>
  damascus model list
  damascus model generate "prompt"
  damascus config health
  damascus tui
"""

from __future__ import annotations

import typer

from damascus_cli.commands import workspace, workflow, memory, config, agent, model

app = typer.Typer(
    name="damascus",
    help="Damascus — Intelligence Operating System CLI",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Register sub-command groups
app.add_typer(workspace.app, name="workspace", help="Manage workspaces")
app.add_typer(workflow.app, name="workflow", help="Manage and run workflows")
app.add_typer(memory.app, name="memory", help="Browse and search memories")
app.add_typer(agent.app, name="agent", help="Manage agent profiles")
app.add_typer(model.app, name="model", help="Manage and use AI model providers")
app.add_typer(config.app, name="config", help="Configuration and health checks")


@app.command("tui")
def launch_tui():
    """Launch the interactive Terminal User Interface (TUI)."""
    from damascus_cli.tui.app import DamascusApp

    app_instance = DamascusApp()
    app_instance.run()


@app.command("version")
def version():
    """Show Damascus version."""
    from rich.console import Console

    Console().print("[bold cyan]Damascus CLI v0.1.0[/bold cyan]")


if __name__ == "__main__":
    app()
