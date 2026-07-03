"""
Damascus TUI — Textual Application
=====================================
Interactive Terminal User Interface for Damascus.
Provides live dashboard, workflow execution view, and memory browser.

Launch with: damascus tui
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)


# ---------------------------------------------------------------------------
# Dashboard Screen
# ---------------------------------------------------------------------------

class DashboardScreen(Screen):
    """Main dashboard showing system status and active workflows."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("w", "workspace", "Workspaces"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent():
            with TabPane("Dashboard", id="dashboard"):
                yield _DashboardPanel()
            with TabPane("Workspaces", id="workspaces"):
                yield _WorkspacePanel()
            with TabPane("Memory", id="memory"):
                yield _MemoryPanel()
        yield Footer()

    def action_refresh(self) -> None:
        """Refresh dashboard data."""
        self.notify("Refreshing…", severity="information")


class _DashboardPanel(Static):
    """System health and active workflow summary."""

    BANNER = """
╔═══════════════════════════════════════════════╗
║         Damascus V1 — Intelligence OS          ║
║                Phase 1 Foundation              ║
╚═══════════════════════════════════════════════╝
"""

    def compose(self) -> ComposeResult:
        yield Label(self.BANNER, id="banner")
        yield Markdown("""
## System Status

Use **Tab** to switch between panels.

Press **q** to quit, **r** to refresh.

### Quick Start

```
damascus workspace create "My Project"
damascus workflow list <workspace_id>
damascus memory search <workspace_id> "query"
```

### API Documentation

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the full API reference.
""")


class _WorkspacePanel(Static):
    """Workspace browser panel."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]Workspaces[/bold]", markup=True)
        yield Label("[dim]Use `damascus workspace list` to view workspaces.[/dim]", markup=True)


class _MemoryPanel(Static):
    """Memory browser panel."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]Memory Browser[/bold]", markup=True)
        yield Label("[dim]Use `damascus memory search <workspace_id> <query>` to search memories.[/dim]", markup=True)


# ---------------------------------------------------------------------------
# Main Textual Application
# ---------------------------------------------------------------------------

class DamascusApp(App):
    """
    Damascus TUI application.
    Built with Textual for a native terminal dashboard experience.
    """

    CSS = """
    Screen {
        background: #1a1b26;
    }
    Header {
        background: #24283b;
        color: #7aa2f7;
    }
    Footer {
        background: #24283b;
    }
    #banner {
        color: #7aa2f7;
        text-align: center;
        padding: 1;
    }
    TabbedContent {
        border: solid #24283b;
    }
    TabPane {
        padding: 1;
    }
    """

    TITLE = "Damascus — Intelligence OS"
    SUB_TITLE = "Phase 1 Foundation"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
    ]

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())
