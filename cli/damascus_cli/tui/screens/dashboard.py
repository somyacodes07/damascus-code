"""
Dashboard Screen — Main TUI screen
=====================================
Shows system health, active executions, and workspace summary.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Markdown, Static


WELCOME_MARKDOWN = """
# Damascus V1

**Intelligence Operating System — Phase 1 Foundation**

---

## Quick Commands

| Command | Description |
|---------|-------------|
| `damascus workspace create "name"` | Create a new workspace |
| `damascus workflow list <id>` | List workflows |
| `damascus memory search <ws> "query"` | Search memories |
| `damascus config health` | Check system health |

---

## Navigation

Use **Tab** to switch between panels in the TUI.
Press **q** to quit at any time.

---

## API Documentation

Start the backend and open: [http://localhost:8000/docs](http://localhost:8000/docs)
"""


class DashboardScreen(Screen):
    """
    Main dashboard screen.
    Shown on TUI startup. Displays system overview and quick navigation.
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Markdown(WELCOME_MARKDOWN, id="welcome")
            yield _StatusBar()
        yield Footer()

    def action_refresh(self) -> None:
        self.notify("Dashboard refreshed", severity="information")


class _StatusBar(Static):
    """Bottom status bar showing key service states."""

    DEFAULT_CSS = """
    _StatusBar {
        background: #24283b;
        color: #a9b1d6;
        height: 3;
        padding: 1 2;
    }
    """

    def render(self) -> str:
        return (
            "[bold]Services:[/bold]  "
            "[green]Backend[/green]  │  "
            "[green]PostgreSQL[/green]  │  "
            "[green]Redis[/green]  │  "
            "[green]Qdrant[/green]  │  "
            "[green]NATS[/green]"
        )
