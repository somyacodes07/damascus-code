"""
Workflow Execution Screen — Live execution view
================================================
Shows a running workflow execution with node status, logs, and controls.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Log, Static


class WorkflowExecutionScreen(Screen):
    """
    Live workflow execution view.
    Polls the backend API for execution state and displays updates.
    """

    BINDINGS = [
        Binding("q", "dismiss", "Back"),
        Binding("p", "pause", "Pause"),
        Binding("c", "cancel", "Cancel"),
    ]

    def __init__(self, execution_id: str) -> None:
        super().__init__()
        self.execution_id = execution_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(f"Execution: [bold]{self.execution_id}[/bold]", markup=True)
        yield Log(id="execution_log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#execution_log", Log)
        log.write_line(f"[{self.execution_id}] Execution started")
        log.write_line("Waiting for workflow nodes to execute…")

    def action_pause(self) -> None:
        self.notify("Pause requested", severity="warning")

    def action_cancel(self) -> None:
        self.notify("Cancel requested", severity="error")
