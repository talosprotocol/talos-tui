"""Inspector screen for detailed audit and governance entries."""
from __future__ import annotations

import json
from typing import Any

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static, Label, Button
from textual.containers import Container, Vertical, VerticalScroll


class InspectorScreen(ModalScreen[None]):
    """Modal screen for inspecting a single structured entry."""

    def __init__(self, title: str, entry: dict[str, Any]):
        super().__init__()
        self.entry_title = title
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield Container(
            Vertical(
                Label(f"INSPECT: {self.entry_title}", id="inspect-title"),
                VerticalScroll(
                    Static(json.dumps(self.entry, indent=2), id="inspect-content"),
                    classes="inspect-scroll"
                ),
                Button("CLOSE", id="btn-inspect-close", variant="primary"),
                id="inspect-dialog"
            ),
            id="inspect-backdrop"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-inspect-close":
            self.app.pop_screen()

    def on_mount(self) -> None:
        self.query_one("#btn-inspect-close").focus()
