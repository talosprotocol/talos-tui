"""Secrets Management Screen for Talos TUI."""
from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Container
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static, Button, Label, Input

from ...core.state import StateStore


class GlassPanel(Container):
    """Stylized container for TUI admin panels."""
    DEFAULT_CSS = """
    GlassPanel {
        border: solid $accent 10%;
        border-title-color: $text-muted;
        background: $surface 30%;
        padding: 1 2;
        margin-bottom: 1;
    }
    """


class SecretsManager(Screen):
    """Admin screen for managing platform secrets and KEK rotation."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("a", "add_secret", "Add Secret"),
        ("d", "delete_selected", "Delete Selected"),
        ("R", "rotate_all", "Rotate All"),
        ("f5", "refresh_data", "Refresh"),
    ]

    def __init__(self, store: StateStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        self._rotation_op_id: str | None = None
        self._rotation_poll_timer: Any | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="secrets-container"):
            # KEK Status Panel
            with GlassPanel(id="kek-panel"):
                yield Static("[bold cyan]KEY ENCRYPTION KEY STATUS[/bold cyan]", classes="panel-title")
                with Horizontal(classes="kek-row"):
                    yield Label("[dim]Current KEK ID:[/dim]  ", classes="label")
                    yield Static("[dim italic]Loading…[/dim italic]", id="current-kek", classes="value mono")
                with Horizontal(classes="kek-row"):
                    yield Label("[dim]Loaded KEKs:  [/dim]  ", classes="label")
                    yield Static("0", id="kek-count", classes="value")
                with Horizontal(classes="kek-row"):
                    yield Label("[dim]Stale Secrets:[/dim]  ", classes="label")
                    yield Static("0", id="stale-count", classes="value amber")
                yield Button(
                    "↺  Rotate All Secrets",
                    variant="warning",
                    id="btn-rotate",
                )

            # Rotation Status Panel (hidden when no active op)
            with GlassPanel(id="rotation-panel"):
                yield Static("[bold amber]ROTATION OPERATION[/bold amber]", classes="panel-title")
                with Horizontal(classes="kek-row"):
                    yield Label("[dim]Op ID:  [/dim]", classes="label")
                    yield Static("—", id="rotation-op-id", classes="value mono")
                with Horizontal(classes="kek-row"):
                    yield Label("[dim]Status: [/dim]", classes="label")
                    yield Static("—", id="rotation-status", classes="value")
                with Horizontal(classes="rotation-stats"):
                    yield Static(" Scanned: [bold]0[/bold]", id="stat-scanned")
                    yield Static(" Rotated: [bold]0[/bold]", id="stat-rotated")
                    yield Static(" Failed: [bold]0[/bold]", id="stat-failed")

            with GlassPanel(id="secret-form-panel"):
                yield Static("[bold cyan]SECRET OPERATIONS[/bold cyan]", classes="panel-title")
                with Horizontal(classes="secret-form-row"):
                    yield Input(placeholder="Secret name", id="secret-name")
                    yield Input(placeholder="Secret value", password=True, id="secret-value")
                with Horizontal(classes="secret-actions"):
                    yield Button("Add Secret", id="btn-add-secret", variant="primary")
                    yield Button("Delete Selected", id="btn-delete-secret", variant="error")

            # Secrets Table
            yield Static("[bold]MANAGED SECRETS REGISTRY[/bold]", classes="panel-title")
            yield DataTable(id="secrets-table", show_cursor=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#secrets-table", DataTable)
        table.add_columns("Secret Name", "KEK ID", "Created At", "Updated At", "Status")
        table.cursor_type = "row"
        self.update_view()
        self.set_interval(2.0, self.update_view)
        # Hide rotation panel until an operation is active
        self.query_one("#rotation-panel").display = False

    def update_view(self) -> None:
        """Update UI from state store."""
        # Update KEK Info
        kek = self.store.kek_status
        if kek:
            self.query_one("#current-kek", Static).update(
                f"[bold #00FF9C]{kek.get('current_kek_id', 'Unknown')}[/bold #00FF9C] "
                "[bold #00FF9C]● ACTIVE[/bold #00FF9C]"
            )
            loaded = kek.get("loaded_kek_ids", [])
            self.query_one("#kek-count", Static).update(str(len(loaded)))
            stale = sum(kek.get("stale_counts", {}).values())
            stale_display = f"[bold #F1FA8C]{stale} STALE[/bold #F1FA8C]" if stale > 0 else "[bold #00FF9C]0[/bold #00FF9C]"
            self.query_one("#stale-count", Static).update(stale_display)

        # Update Secrets Table
        table = self.query_one("#secrets-table", DataTable)
        table.clear()
        current_kek = kek.get("current_kek_id") if kek else None
        
        for s in self.store.secrets:
            kek_id = s.get("kek_id", "")
            is_stale = current_kek and kek_id and kek_id != current_kek
            
            kek_badge = f"[dim]{kek_id[:8]}…[/dim]" if kek_id else "[dim]—[/dim]"
            status = "[bold #00FF9C]● READY[/bold #00FF9C]"
            if is_stale:
                status = "[bold #F1FA8C]▲ STALE[/bold #F1FA8C]"

            table.add_row(
                f"[bold]{s.get('name', '')}[/bold]",
                kek_badge,
                s.get("created_at", "N/A"),
                s.get("updated_at", "N/A"),
                status,
                key=s.get("name")
            )

    def _update_rotation_panel(self, op: dict) -> None:
        """Show and update the rotation operation panel."""
        panel = self.query_one("#rotation-panel")
        panel.display = True

        self.query_one("#rotation-op-id", Static).update(
            f"[dim]{op.get('id', '?')[:16]}…[/dim]"
        )

        status = op.get("status", "unknown")
        status_colors = {"running": "yellow", "completed": "green", "failed": "red"}
        color = status_colors.get(status, "white")
        self.query_one("#rotation-status", Static).update(f"[{color}]{status.upper()}[/{color}]")

        stats = op.get("stats", {})
        self.query_one("#stat-scanned", Static).update(
            f" Scanned: [bold]{stats.get('scanned', 0)}[/bold]"
        )
        self.query_one("#stat-rotated", Static).update(
            f" Rotated: [bold green]{stats.get('rotated', 0)}[/bold green]"
        )
        failed = stats.get("failed", 0)
        failed_color = "red" if failed > 0 else "white"
        self.query_one("#stat-failed", Static).update(
            f" Failed: [bold {failed_color}]{failed}[/bold {failed_color}]"
        )

    def _stop_rotation_polling(self) -> None:
        """Stop any active rotation poll timer once the operation is terminal."""
        if self._rotation_poll_timer is None:
            return
        stop = getattr(self._rotation_poll_timer, "stop", None)
        if callable(stop):
            stop()
        self._rotation_poll_timer = None

    async def _refresh_from_gateway(self, adapter: Any | None = None) -> None:
        """Refresh secrets metadata and KEK state directly from the gateway."""
        active_adapter = adapter or getattr(self.app, "gateway", None)
        if not active_adapter:
            raise RuntimeError("Gateway not connected.")

        secrets = await active_adapter.list_secrets()
        self.store.secrets = [
            secret.model_dump() if hasattr(secret, "model_dump") else secret
            for secret in secrets
        ]

        kek_status = await active_adapter.get_kek_status()
        self.store.kek_status = (
            kek_status.model_dump()
            if hasattr(kek_status, "model_dump")
            else kek_status
        )
        self.update_view()

    def _selected_secret_name(self) -> str | None:
        """Return the currently selected secret name from the registry table."""
        table = self.query_one("#secrets-table", DataTable)
        cursor_row = getattr(table, "cursor_row", None)
        if cursor_row is None:
            return None
        if cursor_row < 0 or cursor_row >= len(self.store.secrets):
            return None
        return str(self.store.secrets[cursor_row].get("name", "")).strip() or None

    @on(Button.Pressed, "#btn-add-secret")
    async def handle_add_secret(self) -> None:
        """Create a secret from the inline form."""
        await self.action_add_secret()

    @on(Button.Pressed, "#btn-delete-secret")
    async def handle_delete_selected(self) -> None:
        """Delete the currently selected secret row."""
        await self.action_delete_selected()

    async def action_refresh_data(self) -> None:
        """Refresh secrets state immediately from the gateway."""
        try:
            await self._refresh_from_gateway()
            self.notify("Secrets refreshed.", title="Secrets")
        except Exception as e:
            self.notify(f"Refresh failed: {e}", severity="error")

    async def action_add_secret(self) -> None:
        """Create a secret from the inline form values."""
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            self.notify("Gateway not connected.", severity="error")
            return

        name_input = self.query_one("#secret-name", Input)
        value_input = self.query_one("#secret-value", Input)
        add_button = self.query_one("#btn-add-secret", Button)
        name = name_input.value.strip()
        value = value_input.value

        if not name or not value:
            self.notify("Enter both secret name and value.", severity="warning")
            return

        add_button.disabled = True
        add_button.label = "Adding..."
        try:
            await adapter.create_secret(name, value)
            await self._refresh_from_gateway(adapter)
            name_input.value = ""
            value_input.value = ""
            self.notify(f"Created secret {name}.", title="Secrets")
        except Exception as e:
            self.notify(f"Create failed: {e}", severity="error")
        finally:
            add_button.disabled = False
            add_button.label = "Add Secret"

    async def action_delete_selected(self) -> None:
        """Delete the currently selected secret from the table."""
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            self.notify("Gateway not connected.", severity="error")
            return

        secret_name = self._selected_secret_name()
        if not secret_name:
            self.notify("Select a secret to delete.", severity="warning")
            return

        delete_button = self.query_one("#btn-delete-secret", Button)
        delete_button.disabled = True
        delete_button.label = "Deleting..."
        try:
            await adapter.delete_secret(secret_name)
            await self._refresh_from_gateway(adapter)
            self.notify(f"Deleted secret {secret_name}.", title="Secrets")
        except Exception as e:
            self.notify(f"Delete failed: {e}", severity="error")
        finally:
            delete_button.disabled = False
            delete_button.label = "Delete Selected"

    @on(Button.Pressed, "#btn-rotate")
    async def action_rotate_all(self) -> None:
        """Initiate KEK rotation via the gateway adapter."""
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            self.notify("Gateway not connected.", severity="error")
            return

        btn = self.query_one("#btn-rotate", Button)
        btn.disabled = True
        btn.label = "⟳  Initiating rotation…"

        try:
            op = await adapter.rotate_all_secrets()
            self._rotation_op_id = op.id
            self._update_rotation_panel(op.model_dump())
            self.notify(
                f"Rotation started: {op.id[:12]}…",
                title="Rotation Initiated",
            )
            # Poll for completion
            self._stop_rotation_polling()
            self._rotation_poll_timer = self.set_interval(2.0, self._poll_rotation)
        except Exception as e:
            self.notify(f"Rotation failed: {e}", severity="error")
            btn.disabled = False
            btn.label = "↺  Rotate All Secrets"
            self._stop_rotation_polling()

    async def _poll_rotation(self) -> None:
        """Poll active rotation operation status."""
        if not self._rotation_op_id:
            return
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            return
        try:
            op = await adapter.get_rotation_status(self._rotation_op_id)
            self._update_rotation_panel(op.model_dump())
            
            # Case-insensitive check for completion
            status_low = op.status.lower()
            if status_low in ("completed", "failed"):
                self._rotation_op_id = None
                self._stop_rotation_polling()
                btn = self.query_one("#btn-rotate", Button)
                btn.disabled = False
                btn.label = "↺  Rotate All Secrets"
                
                if status_low == "completed":
                    stats = op.stats
                    total = stats.get('scanned', 0)
                    rotated = stats.get('rotated', 0)
                    self.notify(
                        f"Successfully rotated {rotated}/{total} secrets.",
                        title="Rotation Complete",
                    )
                else:
                    self.notify(
                        op.last_error or "Unexpected failure during rotation.",
                        title="Rotation Failed",
                        severity="error",
                    )
        except Exception as e:
            self.notify(f"Status poll error: {e}", severity="warning")
