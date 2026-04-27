"""Configuration Management Screen for Talos TUI."""
from __future__ import annotations

import json
from textual.app import ComposeResult
from textual.containers import Vertical, Container, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable, TabbedContent, TabPane

from ...core.state import StateStore


class GlassPanel(Container):
    """Stylized container for TUI config panels."""
    DEFAULT_CSS = """
    GlassPanel {
        border: solid $accent 10%;
        background: $surface 30%;
        padding: 1 2;
        margin-bottom: 1;
    }
    """


class ConfigManager(Screen):
    """Admin screen for inspecting platform configuration — read-only export view."""

    TITLE = "Platform Configuration"
    SUB_TITLE = "Read-only export from /admin/v1/config:export"

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("f5", "refresh_data", "Refresh"),
        ("e", "export_json", "Export JSON"),
    ]

    def __init__(self, store: StateStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-container"):
            yield Static(
                "[bold cyan]PLATFORM CONFIGURATION[/bold cyan]  "
                "[dim]Read-only export • Updates every 30s[/dim]",
                id="config-title"
            )

            with TabbedContent(id="config-tabs"):
                # Tab 1: Upstreams
                with TabPane("LLM Upstreams", id="tab-upstreams"):
                    yield DataTable(id="upstreams-table", show_cursor=True)

                # Tab 2: Model Groups
                with TabPane("Model Groups", id="tab-groups"):
                    yield DataTable(id="groups-table", show_cursor=True)

                # Tab 3: Routing Policies
                with TabPane("Routing Policies", id="tab-policies"):
                    yield DataTable(id="policies-table", show_cursor=True)

                # Tab 4: MCP Servers
                with TabPane("MCP Servers", id="tab-mcp-servers"):
                    yield DataTable(id="mcp-servers-table", show_cursor=True)

                # Tab 5: Raw JSON
                with TabPane("Raw JSON", id="tab-raw"):
                    with ScrollableContainer(id="raw-scroll"):
                        yield Static("", id="config-json", classes="mono-small")

        yield Footer()

    def on_mount(self) -> None:
        # Configure tables
        self.query_one("#upstreams-table", DataTable).add_columns(
            "ID", "Provider", "Endpoint", "Enabled", "Version"
        )
        self.query_one("#groups-table", DataTable).add_columns(
            "ID", "Name", "Deployments", "Routing Policy", "Version"
        )
        self.query_one("#policies-table", DataTable).add_columns(
            "Policy ID", "Version", "Created At"
        )
        self.query_one("#mcp-servers-table", DataTable).add_columns(
            "ID", "Name", "Endpoint", "Enabled", "Version"
        )
        self.update_view()
        self.set_interval(5.0, self.update_view)

    def update_view(self) -> None:
        """Update all config views from state store."""
        config = self.store.platform_config
        if not config:
            self.query_one("#config-json", Static).update(
                "[dim italic]No configuration received yet — waiting for first poll…[/dim italic]"
            )
            return

        # --- Upstreams Tab ---
        upstreams_table = self.query_one("#upstreams-table", DataTable)
        upstreams_table.clear()
        for uid, u in config.get("upstreams", {}).items():
            enabled = "[green]● YES[/green]" if u.get("enabled", True) else "[red]○ NO[/red]"
            endpoint = u.get("endpoint", "—")
            # Truncate long endpoint URLs
            if len(endpoint) > 40:
                endpoint = endpoint[:37] + "…"
            upstreams_table.add_row(
                f"[bold]{uid}[/bold]",
                u.get("provider", "—"),
                f"[dim]{endpoint}[/dim]",
                enabled,
                str(u.get("version", 1)),
            )

        # --- Model Groups Tab ---
        groups_table = self.query_one("#groups-table", DataTable)
        groups_table.clear()
        for gid, g in config.get("model_groups", {}).items():
            dep_count = len(g.get("deployments", []))
            groups_table.add_row(
                f"[bold]{gid}[/bold]",
                g.get("name", "—"),
                str(dep_count),
                g.get("routing_policy_id", "default"),
                str(g.get("version", 1)),
            )

        # --- Policies Tab ---
        policies_table = self.query_one("#policies-table", DataTable)
        policies_table.clear()
        for pid, p in config.get("routing_policies", {}).items():
            policies_table.add_row(
                f"[bold]{pid}[/bold]",
                str(p.get("version", "—")),
                p.get("created_at", "—"),
            )

        # --- MCP Servers Tab ---
        mcp_table = self.query_one("#mcp-servers-table", DataTable)
        mcp_table.clear()
        for sid, s in config.get("mcp_servers", {}).items():
            enabled = "[green]● YES[/green]" if s.get("enabled", True) else "[red]○ NO[/red]"
            mcp_table.add_row(
                f"[bold]{sid}[/bold]",
                s.get("name", "—"),
                f"[dim]{s.get('endpoint', '—')}[/dim]",
                enabled,
                str(s.get("version", 1)),
            )

        # --- Raw JSON Tab ---
        formatted = json.dumps(config, indent=2)
        self.query_one("#config-json", Static).update(formatted)

    async def action_refresh_data(self) -> None:
        """Refresh the configuration snapshot immediately from the gateway."""
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            self.notify("Gateway not connected.", severity="error")
            return
        try:
            config = await adapter.export_config()
            self.store.platform_config = (
                config.model_dump() if hasattr(config, "model_dump") else config
            )
            self.update_view()
            self.notify("Configuration refreshed.", title="Config")
        except Exception as e:
            self.notify(f"Refresh failed: {e}", severity="error")

    def action_export_json(self) -> None:
        """Export current config to a file."""
        config = self.store.platform_config
        if not config:
            self.notify("No config loaded yet.", severity="warning")
            return
        try:
            import datetime
            filename = f"talos-config-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            with open(filename, "w") as f:
                json.dump(config, f, indent=2)
            self.notify(f"Exported to {filename}", title="Config Exported")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")
