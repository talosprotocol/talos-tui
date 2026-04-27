"""MCP management screen for Talos TUI."""
from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static, TabbedContent, TabPane
from rich.text import Text

from ...core.state import StateStore


class McpManager(Screen):
    """Inspect MCP servers and policies loaded from the gateway."""

    TITLE = "MCP"
    SUB_TITLE = "Servers and policies"

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("f5", "refresh_data", "Refresh"),
        ("d", "delete_selected", "Delete Selected"),
    ]

    def __init__(self, store: StateStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="mcp-container"):
            yield Static(
                "[bold cyan]MODEL CONTEXT PROTOCOL CONTROL[/bold cyan]  "
                "[dim]Servers • Policies • Enforcement[/dim]",
                id="mcp-title",
            )
            with TabbedContent(id="mcp-tabs"):
                with TabPane("Servers", id="tab-mcp-servers"):
                    with Horizontal(classes="mcp-form-row"):
                        yield Input(placeholder="Server ID", id="mcp-server-id")
                        yield Input(placeholder="Name", id="mcp-server-name")
                        yield Input(placeholder="Endpoint", id="mcp-server-endpoint")
                    with Horizontal(classes="mcp-actions"):
                        yield Button("Add Server", id="btn-mcp-add-server", variant="primary")
                        yield Button("Enable", id="btn-mcp-enable-server")
                        yield Button("Disable", id="btn-mcp-disable-server", variant="warning")
                        yield Button("Delete", id="btn-mcp-delete-server", variant="error")
                    yield DataTable(id="mcp-servers-table", show_cursor=True, zebra_stripes=True)
                with TabPane("Policies", id="tab-mcp-policies"):
                    with Vertical(classes="mcp-form-panel"):
                        yield Static("[bold cyan]CREATE/UPDATE POLICY[/bold cyan]", classes="panel-title")
                        with Horizontal(classes="mcp-form-row"):
                            yield Input(placeholder="Policy ID", id="mcp-policy-id")
                            yield Input(placeholder="Team ID", id="mcp-policy-team-id")
                            yield Input(placeholder="Allowed Servers (comma separated)", id="mcp-policy-servers")
                        with Horizontal(classes="mcp-actions"):
                            yield Button("Upsert Policy", id="btn-mcp-upsert-policy", variant="primary")
                            yield Button("Delete Selected", id="btn-mcp-delete-policy", variant="error")
                    yield DataTable(id="mcp-policies-table", show_cursor=True, zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        servers_table = self.query_one("#mcp-servers-table", DataTable)
        servers_table.add_columns("ID", "Name", "Endpoint", "Enabled", "Version")

        policies_table = self.query_one("#mcp-policies-table", DataTable)
        policies_table.add_columns("Policy ID", "Team", "Allowed Servers", "Mode")

        self.update_view()
        self.set_interval(2.0, self.update_view)

    def update_view(self) -> None:
        """Project MCP state to the operator tables."""
        servers_table = self.query_one("#mcp-servers-table", DataTable)
        servers_table.clear()
        for server in self.store.mcp_servers:
            enabled = "[green]YES[/green]" if server.get("enabled", True) else "[red]NO[/red]"
            servers_table.add_row(
                Text(server.get("id", "—"), style="bold cyan"),
                server.get("name", "—"),
                server.get("endpoint", "—"),
                enabled,
                str(server.get("version", "—")),
            )

        policies_table = self.query_one("#mcp-policies-table", DataTable)
        policies_table.clear()
        for policy in self.store.mcp_policies:
            allowed_servers = ", ".join(policy.get("allowed_servers", [])) or "—"
            policies_table.add_row(
                Text(policy.get("id", "—"), style="bold magenta"),
                policy.get("team_id", "—"),
                allowed_servers,
                policy.get("enforcement_mode", "strict").upper(),
            )

    def _selected_server_id(self) -> str | None:
        """Return the selected MCP server id from the registry table."""
        table = self.query_one("#mcp-servers-table", DataTable)
        cursor_row = getattr(table, "cursor_row", None)
        if cursor_row is None:
            return None
        if cursor_row < 0 or cursor_row >= len(self.store.mcp_servers):
            return None
        return str(self.store.mcp_servers[cursor_row].get("id", "")).strip() or None

    def _policy_team_filter(self) -> str | None:
        """Return the optional policy team filter if the input is mounted."""
        try:
            value = self.query_one("#mcp-policy-team", Input).value
        except Exception:
            return None
        return value.strip() or None

    async def _refresh_from_gateway(self, adapter: Any | None = None) -> None:
        """Refresh MCP state from the gateway API."""
        active_adapter = adapter or getattr(self.app, "gateway", None)
        if not active_adapter:
            raise RuntimeError("Gateway not connected.")

        servers = await active_adapter.list_mcp_servers()
        policies = await active_adapter.list_mcp_policies(team_id=self._policy_team_filter())
        self.store.mcp_servers = [
            server.model_dump() if hasattr(server, "model_dump") else server
            for server in servers
        ]
        self.store.mcp_policies = [
            policy.model_dump() if hasattr(policy, "model_dump") else policy
            for policy in policies
        ]
        self.update_view()

    @on(Button.Pressed, "#btn-mcp-add-server")
    async def handle_add_server(self) -> None:
        """Create a server from the inline form."""
        await self.action_add_server()

    @on(Button.Pressed, "#btn-mcp-enable-server")
    async def handle_enable_selected(self) -> None:
        """Enable the selected server."""
        await self.action_enable_selected()

    @on(Button.Pressed, "#btn-mcp-disable-server")
    async def handle_disable_selected(self) -> None:
        """Disable the selected server."""
        await self.action_disable_selected()

    @on(Button.Pressed, "#btn-mcp-delete-server")
    async def handle_delete_selected(self) -> None:
        """Delete the selected server."""
        await self.action_delete_selected()

    def _selected_policy_id(self) -> str | None:
        """Return the selected MCP policy id from the registry table."""
        table = self.query_one("#mcp-policies-table", DataTable)
        cursor_row = getattr(table, "cursor_row", None)
        if cursor_row is None:
            return None
        if cursor_row < 0 or cursor_row >= len(self.store.mcp_policies):
            return None
        return str(self.store.mcp_policies[cursor_row].get("id", "")).strip() or None

    @on(Button.Pressed, "#btn-mcp-upsert-policy")
    async def handle_upsert_policy(self) -> None:
        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        pid = self.query_one("#mcp-policy-id", Input).value.strip()
        tid = self.query_one("#mcp-policy-team-id", Input).value.strip()
        servers = [s.strip() for s in self.query_one("#mcp-policy-servers", Input).value.split(",") if s.strip()]

        if not pid or not tid:
            self.notify("Enter Policy ID and Team ID", severity="warning")
            return

        try:
            await adapter.upsert_mcp_policy({
                "id": pid, "team_id": tid, "allowed_servers": servers
            })
            self.notify(f"Upserted policy {pid}")
            self.query_one("#mcp-policy-id", Input).value = ""
            self.query_one("#mcp-policy-team-id", Input).value = ""
            self.query_one("#mcp-policy-servers", Input).value = ""
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-mcp-delete-policy")
    async def handle_delete_policy(self) -> None:
        pid = self._selected_policy_id()
        if not pid:
            self.notify("Select a policy to delete", severity="warning")
            return

        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        try:
            await adapter.delete_mcp_policy(pid)
            self.notify(f"Deleted policy {pid}")
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-mcp-refresh-policies")
    async def handle_refresh_policies(self) -> None:
        """Refresh policy rows using the current team filter."""
        await self.action_refresh_data()

    async def action_refresh_data(self) -> None:
        """Refresh MCP state directly from the gateway."""
        try:
            await self._refresh_from_gateway()
            self.notify("MCP state refreshed.", title="MCP")
        except Exception as e:
            self.notify(f"Refresh failed: {e}", severity="error")

    async def action_add_server(self) -> None:
        """Create an MCP server via the gateway API."""
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            self.notify("Gateway not connected.", severity="error")
            return

        server_id = self.query_one("#mcp-server-id", Input).value.strip()
        name = self.query_one("#mcp-server-name", Input).value.strip()
        endpoint = self.query_one("#mcp-server-endpoint", Input).value.strip()
        if not server_id:
            self.notify("Enter an MCP server id.", severity="warning")
            return

        button = self.query_one("#btn-mcp-add-server", Button)
        button.disabled = True
        try:
            payload = {
                "id": server_id,
                "name": name or server_id,
                "endpoint": endpoint,
                "transport": "http",
                "enabled": True,
            }
            await adapter.create_mcp_server(payload)
            await self._refresh_from_gateway(adapter)
            self.query_one("#mcp-server-id", Input).value = ""
            self.query_one("#mcp-server-name", Input).value = ""
            self.query_one("#mcp-server-endpoint", Input).value = ""
            self.notify(f"Created MCP server {server_id}.", title="MCP")
        except Exception as e:
            self.notify(f"Create failed: {e}", severity="error")
        finally:
            button.disabled = False

    async def _set_selected_enabled(self, enabled: bool) -> None:
        """Enable or disable the selected MCP server."""
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            self.notify("Gateway not connected.", severity="error")
            return
        server_id = self._selected_server_id()
        if not server_id:
            self.notify("Select an MCP server first.", severity="warning")
            return

        try:
            if enabled:
                await adapter.enable_mcp_server(server_id)
            else:
                await adapter.disable_mcp_server(server_id)
            await self._refresh_from_gateway(adapter)
            action = "Enabled" if enabled else "Disabled"
            self.notify(f"{action} MCP server {server_id}.", title="MCP")
        except Exception as e:
            self.notify(f"Update failed: {e}", severity="error")

    async def action_enable_selected(self) -> None:
        """Enable the currently selected MCP server."""
        await self._set_selected_enabled(True)

    async def action_disable_selected(self) -> None:
        """Disable the currently selected MCP server."""
        await self._set_selected_enabled(False)

    async def action_delete_selected(self) -> None:
        """Delete the currently selected MCP server."""
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            self.notify("Gateway not connected.", severity="error")
            return
        server_id = self._selected_server_id()
        if not server_id:
            self.notify("Select an MCP server first.", severity="warning")
            return

        button = self.query_one("#btn-mcp-delete-server", Button)
        button.disabled = True
        try:
            await adapter.delete_mcp_server(server_id)
            await self._refresh_from_gateway(adapter)
            self.notify(f"Deleted MCP server {server_id}.", title="MCP")
        except Exception as e:
            self.notify(f"Delete failed: {e}", severity="error")
        finally:
            button.disabled = False
