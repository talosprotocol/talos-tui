"""Secrets Management Screen for Talos TUI."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Container
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static, Button, Label, LoadingIndicator

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
        ("R", "rotate_all", "Rotate All"),
        ("f5", "refresh_data", "Refresh"),
    ]

    def __init__(self, store: StateStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        self._rotation_op_id: str | None = None

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
            self.query_one("#current-kek", Static).update(kek.get("current_kek_id", "Unknown"))
            loaded = kek.get("loaded_kek_ids", [])
            self.query_one("#kek-count", Static).update(str(len(loaded)))
            stale = sum(kek.get("stale_counts", {}).values())
            stale_display = f"[yellow]{stale}[/yellow]" if stale > 0 else "[green]0[/green]"
            self.query_one("#stale-count", Static).update(stale_display)

        # Update Secrets Table
        table = self.query_one("#secrets-table", DataTable)
        table.clear()
        for s in self.store.secrets:
            kek_id = s.get("kek_id", "")
            kek_badge = f"[dim]{kek_id[:8]}…[/dim]" if kek_id else "[dim]—[/dim]"
            table.add_row(
                f"[bold]{s.get('name', '')}[/bold]",
                kek_badge,
                s.get("created_at", "N/A"),
                s.get("updated_at", "N/A"),
                "[green]● READY[/green]",
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
            self.set_interval(2.0, self._poll_rotation)
        except Exception as e:
            self.notify(f"Rotation failed: {e}", severity="error")
            btn.disabled = False
            btn.label = "↺  Rotate All Secrets"

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
