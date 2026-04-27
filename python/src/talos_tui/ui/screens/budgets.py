"""Budget and Key Management Screen for Talos TUI."""
from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable, TabbedContent, TabPane, Input, Button
from rich.text import Text

from ...core.state import StateStore


class BudgetManager(Screen):
    """Admin screen for managing and monitoring budgets and keys."""

    TITLE = "Budgets & Keys"
    SUB_TITLE = "Monitor usage and manage limits"

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("f5", "refresh_data", "Refresh"),
    ]

    def __init__(self, store: StateStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        self._last_scopes_count = -1
        self._last_keys_count = -1
        self._last_teams_count = -1

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="budgets-container"):
            yield Static(
                "[bold cyan]BUDGET & KEY MISSION CONTROL[/bold cyan]  "
                "[dim]Live Usage • Limits • Team Hierarchy[/dim]",
                id="budgets-title"
            )

            with TabbedContent(id="budgets-tabs"):
                with TabPane("Live Usage", id="tab-usage"):
                    yield DataTable(id="usage-table", show_cursor=True, zebra_stripes=True)

                with TabPane("Virtual Keys", id="tab-keys"):
                    with Vertical(classes="mcp-form-panel"):
                        yield Static("[bold cyan]CREATE VIRTUAL KEY[/bold cyan]", classes="panel-title")
                        with Horizontal(classes="mcp-form-row"):
                            yield Input(placeholder="Key ID (e.g. tk_123)", id="key-id")
                            yield Input(placeholder="Team ID", id="key-team-id")
                            yield Input(placeholder="Limit USD", id="key-limit")
                        with Horizontal(classes="mcp-actions"):
                            yield Button("Add Key", id="btn-add-key", variant="primary")
                            yield Button("Revoke Selected", id="btn-revoke-key", variant="error")
                    yield DataTable(id="keys-table", show_cursor=True, zebra_stripes=True)

                with TabPane("Teams", id="tab-teams"):
                    with Vertical(classes="mcp-form-panel"):
                        yield Static("[bold cyan]CREATE TEAM[/bold cyan]", classes="panel-title")
                        with Horizontal(classes="mcp-form-row"):
                            yield Input(placeholder="Team ID", id="team-id")
                            yield Input(placeholder="Team Name", id="team-name")
                            yield Input(placeholder="Budget USD", id="team-limit")
                        with Horizontal(classes="mcp-actions"):
                            yield Button("Add Team", id="btn-add-team", variant="primary")
                    yield DataTable(id="teams-table", show_cursor=True, zebra_stripes=True)

        yield Footer()

    def on_mount(self) -> None:
        # Configure tables
        usage_table = self.query_one("#usage-table", DataTable)
        usage_table.add_columns("Scope", "ID", "Limit (USD)", "Used", "Reserved", "Status")

        keys_table = self.query_one("#keys-table", DataTable)
        keys_table.add_columns("ID", "Team", "Mode", "Limit", "Overdraft", "Revoked")

        teams_table = self.query_one("#teams-table", DataTable)
        teams_table.add_columns("ID", "Name", "Mode", "Limit", "Overdraft")

        self.update_view()
        self.set_interval(2.0, self.update_view)

    def update_view(self) -> None:
        """Update views from state store."""
        self._refresh_usage()
        self._refresh_keys()
        self._refresh_teams()

    async def action_refresh_data(self) -> None:
        """Refresh budget, key, and team data directly from the gateway."""
        adapter = getattr(self.app, "gateway", None)
        if not adapter:
            self.notify("Gateway not connected.", severity="error")
            return
        try:
            scopes = await adapter.list_budget_scopes()
            keys = await adapter.list_virtual_keys()
            teams = await adapter.list_teams()
            self.store.budget_scopes = [
                scope.model_dump() if hasattr(scope, "model_dump") else scope
                for scope in scopes
            ]
            self.store.virtual_keys = [
                key.model_dump() if hasattr(key, "model_dump") else key
                for key in keys
            ]
            self.store.teams = [
                team.model_dump() if hasattr(team, "model_dump") else team
                for team in teams
            ]
            self.update_view()
            self.notify("Budgets refreshed.", title="Budgets")
        except Exception as e:
            self.notify(f"Refresh failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-add-team")
    async def handle_add_team(self) -> None:
        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        tid = self.query_one("#team-id", Input).value.strip()
        name = self.query_one("#team-name", Input).value.strip()
        limit = self.query_one("#team-limit", Input).value.strip() or "0"

        if not tid or not name:
            self.notify("Enter Team ID and Name", severity="warning")
            return

        try:
            await adapter._request("POST", "admin/v1/teams", json_data={
                "id": tid, "name": name, "budget_mode": "hard", "budget": {"limit_usd": float(limit)}
            })
            self.notify(f"Created team {tid}")
            self.query_one("#team-id", Input).value = ""
            self.query_one("#team-name", Input).value = ""
            self.query_one("#team-limit", Input).value = ""
            await self.action_refresh_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-add-key")
    async def handle_add_key(self) -> None:
        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        kid = self.query_one("#key-id", Input).value.strip()
        tid = self.query_one("#key-team-id", Input).value.strip()
        limit = self.query_one("#key-limit", Input).value.strip() or "0"

        if not kid or not tid:
            self.notify("Enter Key ID and Team ID", severity="warning")
            return

        try:
            await adapter._request("POST", "admin/v1/keys", json_data={
                "id": kid, "team_id": tid, "budget_mode": "hard", "budget": {"limit_usd": float(limit)}
            })
            self.notify(f"Created key {kid}")
            self.query_one("#key-id", Input).value = ""
            self.query_one("#key-team-id", Input).value = ""
            self.query_one("#key-limit", Input).value = ""
            await self.action_refresh_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-revoke-key")
    async def handle_revoke_key(self) -> None:
        table = self.query_one("#keys-table", DataTable)
        if table.cursor_row < 0: return
        key_id = table.get_row_at(table.cursor_row)[0].plain
        
        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        try:
            await adapter._request("POST", f"admin/v1/keys/{key_id}:revoke")
            self.notify(f"Revoked key {key_id}")
            await self.action_refresh_data()
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    def _refresh_usage(self) -> None:
        scopes = self.store.budget_scopes
        table = self.query_one("#usage-table", DataTable)
        table.clear()

        for s in scopes:
            limit = float(s.get("limit_usd", 0))
            used = float(s.get("used_usd", 0))
            reserved = float(s.get("reserved_usd", 0))
            total = used + reserved
            
            status = "[green]OK[/green]"
            if limit > 0:
                if total >= limit:
                    status = "[red]EXCEEDED[/red]"
                elif total >= limit * 0.8:
                    status = "[yellow]WARNING[/yellow]"

            table.add_row(
                Text(s.get("scope_type", "—").upper(), style="bold"),
                s.get("scope_id", "—"),
                f"${limit:,.4f}",
                f"${used:,.4f}",
                f"[dim]${reserved:,.4f}[/dim]",
                status
            )

    def _refresh_keys(self) -> None:
        keys = self.store.virtual_keys
        table = self.query_one("#keys-table", DataTable)
        table.clear()

        for k in keys:
            revoked = "[red]YES[/red]" if k.get("revoked") else "[green]NO[/green]"
            limit = k.get("budget", {}).get("limit_usd", "0")
            
            table.add_row(
                Text(k.get("id", "—"), style="bold cyan"),
                k.get("team_id", "—"),
                k.get("budget_mode", "off").upper(),
                f"${float(limit):.2f}",
                f"${float(k.get('overdraft_usd', 0)):.2f}",
                revoked
            )

    def _refresh_teams(self) -> None:
        teams = self.store.teams
        table = self.query_one("#teams-table", DataTable)
        table.clear()

        for t in teams:
            limit = t.get("budget", {}).get("limit_usd", "0")
            table.add_row(
                Text(t.get("id", "—"), style="bold magenta"),
                t.get("name", "—"),
                t.get("budget_mode", "off").upper(),
                f"${float(limit):.2f}",
                f"${float(t.get('overdraft_usd', 0)):.2f}"
            )
