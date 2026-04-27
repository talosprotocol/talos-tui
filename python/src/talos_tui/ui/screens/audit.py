"""Module for the AuditViewer screen in the Talos TUI."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Container, Horizontal
from rich.text import Text

from talos_tui.core.state import StateStore
from .inspect import InspectorScreen


class AuditViewer(Screen[None]):
    """Screen for viewing audit events logs."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("space", "toggle_pause", "Pause/Resume"),
        ("f5", "refresh_view", "Refresh"),
        ("enter", "inspect_event", "Inspect"),
    ]


    def __init__(self, store: StateStore):
        super().__init__()
        self.store = store
        self._last_event_count = 0
        self.is_paused = False

    def compose(self) -> ComposeResult:
        """Compose the screen interface."""
        yield Header()
        with Container(id="audit_container"):
            with Horizontal(id="audit-header"):
                yield Label("AUDIT EVENT LOG", classes="title")
                yield Label("", id="pause-indicator", classes="stale-warning")
            yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the data table columns and start the refresh interval."""
        table = self.query_one(DataTable)
        table.add_columns("!", "Timestamp", "Type", "Proof", "ID")
        self.set_interval(1.0, self.refresh_view)

    def action_toggle_pause(self) -> None:
        """Toggle the live stream pause state."""
        self.is_paused = not self.is_paused
        indicator = self.query_one("#pause-indicator", Label)
        if self.is_paused:
            indicator.update("PAUSED")
            indicator.display = True
        else:
            indicator.display = False

    def action_inspect_event(self) -> None:
        """Inspect the selected event in a modal."""
        table = self.query_one(DataTable)
        cursor_row = getattr(table, "cursor_row", None)
        if cursor_row is None or cursor_row < 0:
            return

        # Map back to store index (events are newest first, but table is newest at bottom usually)
        # However, refresh_view reverses them before adding.
        # Let's find by ID which is safer.
        row = table.get_row_at(cursor_row)
        # ID is at index 4
        event_id = str(row[4].plain)
        
        event = next((e for e in self.store.audit_events if e.get("event_id") == event_id or e.get("id") == event_id), None)
        if event:
            self.app.push_screen(InspectorScreen(f"Event {event_id}", event))

    def refresh_view(self) -> None:
        """Project current StateStore audit events to UI"""
        if self.is_paused:
            return

        events = self.store.audit_events
        if len(events) == self._last_event_count:
            return

        table = self.query_one(DataTable)
        if len(events) < self._last_event_count:
            table.clear()
            self._last_event_count = 0

        # Add only new events
        new_events = events[:len(events) - self._last_event_count]
        for e in reversed(new_events):
            sev_char, color = self._get_severity(e.get("outcome", "OK"))

            display_type = (
                e.get("event_type") or e.get("schema_id") or "unknown"
            ).replace("talos.", "")
            eid = e.get("event_id") or e.get("id") or "unknown"
            ts = e.get("ts") or "unknown"
            
            # Integrity/Proof badge
            integrity = e.get("integrity", {})
            proof_state = integrity.get("proof_state", "UNVERIFIED")
            proof_text, proof_style = self._get_proof_style(proof_state, integrity.get("failure_reason"))

            table.add_row(
                Text(sev_char, style=f"bold {color}"),
                Text(ts, style=color),
                Text(
                    f"{display_type} ({e.get('outcome', 'OK')})", style=color
                ),
                Text(proof_text, style=proof_style),
                Text(eid, style="dim")
            )

        self._last_event_count = len(events)
        table.scroll_end(animate=False)

    def _get_severity(self, outcome: str) -> tuple[str, str]:
        outcome = outcome.upper()
        if outcome == "ERROR":
            return "E", "#FF007A"
        if outcome == "DENY":
            return "W", "#F1FA8C"
        return "I", "#00FF9C"

    def _get_proof_style(self, state: str, reason: str | None) -> tuple[str, str]:
        if reason == "CURSOR_MISMATCH":
            return "TAMPERED", "bold #FF007A animate-pulse"
        if state == "VERIFIED":
            return "VERIFIED", "#00FF9C"
        if state == "FAILED":
            return "FAILED", "#FF007A"
        if state == "MISSING_INPUTS":
            return "MISSING", "#F1FA8C"
        return "UNVERIFIED", "dim"
