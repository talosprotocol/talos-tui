"""Budget and Key Management Screen for Talos TUI."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Container
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, DataTable, TabbedContent, TabPane
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
                    yield DataTable(id="keys-table", show_cursor=True, zebra_stripes=True)

                with TabPane("Teams", id="tab-teams"):
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
