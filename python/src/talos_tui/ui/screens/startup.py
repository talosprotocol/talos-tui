from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, LoadingIndicator, Button
from textual.containers import Vertical, Horizontal, Container
from textual.message import Message

from talos_tui.core.state import StateStore, SourceState

class StartupScreen(Screen):
    """
    StartupScreen: 
    - Real-time status for Gateway and Audit.
    - Retry budget display.
    - Fatal error remediation hints.
    """
    
    DEFAULT_CSS = """
    StartupScreen {
        align: center middle;
        background: $background;
    }
    .startup-panel {
        width: 60;
        height: auto;
        border: thick $primary;
        padding: 1 2;
        background: $surface;
    }
    .status-row {
        height: 1;
        margin: 1 0;
    }
    .status-ok {
        color: $success;
    }
    .status-error {
        color: $error;
    }
    .status-pending {
        color: $warning;
    }
    .error-hint {
        color: $warning;
        italic: True;
        margin-top: 1;
    }
    """

    def __init__(self, store: StateStore):
        super().__init__()
        self.store = store

    def compose(self) -> ComposeResult:
        with Container(classes="startup-panel"):
            yield Label("TALOS COMMAND CENTER", id="title")
            yield Label("Initializing Secure Links...", id="subtitle")
            
            with Vertical(id="status-container"):
                yield Horizontal(
                    Label("Gateway: ", classes="label"),
                    Label("WAITING", id="gw-status", classes="status-pending"),
                    classes="status-row"
                )
                yield Horizontal(
                    Label("Audit Log: ", classes="label"),
                    Label("WAITING", id="audit-status", classes="status-pending"),
                    classes="status-row"
                )
            
            yield Label("", id="error-hint", classes="error-hint")
            
            yield LoadingIndicator(id="loading")
            
            with Horizontal(id="actions", variant="hidden"):
                yield Button("Retry", id="retry-btn", variant="primary")
                yield Button("Quit", id="quit-btn", variant="error")

    def on_mount(self) -> None:
        self.set_interval(0.5, self.update_status)

    def update_status(self) -> None:
        """Refresh UI from store state"""
        self._update_source("gw-status", self.store.gateway)
        self._update_source("audit-status", self.store.audit)
        
        if self.store.global_error:
            self.query_one("#error-hint", Label).update(self.store.global_error)
            # Switch to fatal UI if needed
            if self.store.is_fatal:
                 self.query_one("#loading").display = False
        else:
             self.query_one("#error-hint", Label).update("")

    def _update_source(self, widget_id: str, state: SourceState) -> None:
        label = self.query_one(f"#{widget_id}", Label)
        if state.health_ok:
            label.update("CONNECTED")
            label.set_classes("status-ok")
        elif state.error:
            label.update(f"ERROR: {state.error}")
            label.set_classes("status-error")
        else:
            label.update(state.status_msg)
            label.set_classes("status-pending")
