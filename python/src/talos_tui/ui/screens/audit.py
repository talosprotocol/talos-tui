from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Container
from rich.text import Text

from talos_tui.core.state import StateStore


class AuditViewer(Screen):
    def __init__(self, store: StateStore):
        super().__init__()
        self.store = store
        self._last_event_count = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="audit_container"):
            yield Label("AUDIT EVENT LOG", classes="title")
            yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("!", "Timestamp", "Type", "ID")
        self.set_interval(1.0, self.refresh_view)

    def refresh_view(self) -> None:
        """Project current StateStore audit events to UI"""
        events = self.store.audit_events
        if len(events) == self._last_event_count:
            return

        table = self.query_one(DataTable)
        # For simplicity in this redraw, we check if we need to sync
        # In a real app we might only append, but since store is the truth:
        if len(events) < self._last_event_count:
            table.clear()
            self._last_event_count = 0

        # Add only new events (events are sorted newest first in store)
        new_events = events[:len(events) - self._last_event_count]
        # Reverse to add to table (which appends)
        for e in reversed(new_events):
            sev_char, color = self._get_severity(e.get("outcome", "OK"))

            display_type = (
                e.get("event_type") or e.get("schema_id") or "unknown"
            ).replace("talos.", "")
            eid = e.get("event_id") or e.get("id") or "unknown"
            ts = e.get("ts") or "unknown"

            table.add_row(
                Text(sev_char, style=f"bold {color}"),
                Text(ts, style=color),
                Text(
                    f"{display_type} ({e.get('outcome', 'OK')})", style=color
                ),
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
