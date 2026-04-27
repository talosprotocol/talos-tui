"""Module for the GovernanceViewer screen in the Talos TUI."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Container
from rich.text import Text

from talos_tui.core.state import StateStore
from .inspect import InspectorScreen


class GovernanceViewer(Screen[None]):
    """Screen for viewing high-integrity governance execution logs."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("f5", "refresh_view", "Refresh"),
        ("enter", "inspect_entry", "Inspect"),
    ]

    def __init__(self, store: StateStore):
        super().__init__()
        self.store = store
        self._last_log_count = 0

    def action_inspect_entry(self) -> None:
        """Inspect the selected governance entry."""
        table = self.query_one(DataTable)
        cursor_row = getattr(table, "cursor_row", None)
        if cursor_row is None or cursor_row < 0:
            return

        row = table.get_row_at(cursor_row)
        # Trace ID is at index 3
        trace_id = str(row[3].plain)
        
        entry = next((l for l in self.store.governance_logs if l.get("trace_id", "").startswith(trace_id)), None)
        if entry:
            self.app.push_screen(InspectorScreen(f"Governance {trace_id}", entry))

    def compose(self) -> ComposeResult:
        """Compose the screen interface."""
        yield Header()
        with Container(id="gov_container"):
            yield Label("GOVERNANCE EXECUTION LOG (TGA)", classes="title")
            yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the data table columns and start the refresh interval."""
        table = self.query_one(DataTable)
        # Sequence, Time, Type, Trace ID, Principal
        table.add_columns("Seq", "Timestamp", "Type", "Trace ID", "Principal", "Integrity")
        self.set_interval(1.0, self.refresh_view)

    def refresh_view(self) -> None:
        """Project current StateStore governance logs to UI"""
        logs = self.store.governance_logs
        if len(logs) == self._last_log_count:
            return

        table = self.query_one(DataTable)
        
        if len(logs) < self._last_log_count:
            table.clear()
            self._last_log_count = 0

        # Add only new items
        new_logs = logs[:len(logs) - self._last_log_count]
        # Reverse to add to table (which appends)
        for l in reversed(new_logs):
            status = l.get("status", "VALIDATED")
            color = "#00FF9C" if status == "VALIDATED" else "#F1FA8C"
            
            ts = l.get("ts", "unknown")
            if "T" in ts:
                ts = ts.split("T")[1].split(".")[0]
            
            table.add_row(
                Text(str(l.get("sequence_number")), style="bold"),
                Text(ts, style="dim"),
                Text(l.get("artifact_type", "unknown"), style="#BD93F9"),
                Text(l.get("trace_id", "unknown")[:12], style="italic"),
                Text(l.get("principal_id", "admin")[:12], style="#8BE9FD"),
                Text(status, style=f"bold {color}")
            )

        self._last_log_count = len(logs)
        table.scroll_end(animate=False)
