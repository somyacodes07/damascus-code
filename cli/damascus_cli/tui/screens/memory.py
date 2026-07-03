"""
Memory Browser Screen — Semantic memory search in TUI
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Log, Static


class MemoryBrowserScreen(Screen):
    """
    Interactive memory search screen.
    Allows typing a query and viewing semantic search results.
    """

    BINDINGS = [
        Binding("q", "dismiss", "Back"),
        Binding("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self, workspace_id: str) -> None:
        super().__init__()
        self.workspace_id = workspace_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(f"Memory Browser — Workspace: [bold]{self.workspace_id}[/bold]", markup=True)
        yield Input(placeholder="Search memories…", id="query_input")
        yield Log(id="results_log", auto_scroll=True)
        yield Footer()

    def action_clear(self) -> None:
        self.query_one("#results_log", Log).clear()
