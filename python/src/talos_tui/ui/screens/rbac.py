"""Module for the RBAC management screen in the Talos TUI."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label, TabbedContent, TabPane
from textual.containers import Container
from rich.text import Text

from talos_tui.core.state import StateStore


class RbacManager(Screen[None]):
    """Screen for managing RBAC roles and bindings."""
    def __init__(self, store: StateStore):
        super().__init__()
        self.store = store
        self._last_roles_count = -1
        self._last_bindings_count = -1

    def compose(self) -> ComposeResult:
        """Compose the screen interface."""
        yield Header()
        with Container(id="rbac_container"):
            yield Label("RBAC MISSION CONTROL", classes="title")
            with TabbedContent():
                with TabPane("Roles", id="tab_roles"):
                    yield DataTable(id="table_roles", cursor_type="row", zebra_stripes=True)
                with TabPane("Bindings", id="tab_bindings"):
                    yield DataTable(id="table_bindings", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the data tables and start the refresh interval."""
        roles_table = self.query_one("#table_roles", DataTable)
        roles_table.add_columns("ID", "Name", "Permissions", "Built-in")

        bindings_table = self.query_one("#table_bindings", DataTable)
        bindings_table.add_columns("Principal", "Roles & Scopes")

        self.set_interval(1.0, self.refresh_view)

    def refresh_view(self) -> None:
        """Project current StateStore RBAC data to UI."""
        self._refresh_roles()
        self._refresh_bindings()

    def _refresh_roles(self) -> None:
        roles = self.store.rbac_roles
        if len(roles) == self._last_roles_count:
            return

        table = self.query_one("#table_roles", DataTable)
        table.clear()

        for r in roles:
            role_id = r.get("role_id", "unknown")
            name = r.get("name", "unknown")
            perms = ", ".join(r.get("permissions", []))
            built_in = "YES" if r.get("built_in") else "NO"

            table.add_row(
                Text(role_id, style="bold #14FFEC"),
                Text(name),
                Text(perms, style="dim"),
                Text(built_in, style="#7AA2F7" if built_in == "YES" else "")
            )

        self._last_roles_count = len(roles)

    def _refresh_bindings(self) -> None:
        bindings = self.store.rbac_bindings
        if len(bindings) == self._last_bindings_count:
            return

        table = self.query_one("#table_bindings", DataTable)
        table.clear()

        for b in bindings:
            principal = b.get("principal_id", "unknown")
            
            # Format bindings entries
            entries = b.get("bindings", [])
            formatted_entries = []
            for entry in entries:
                rid = entry.get("role_id", "unknown")
                scope = entry.get("scope", {})
                stype = scope.get("scope_type", "global")
                formatted_entries.append(f"{rid} [{stype}]")
            
            display_entries = " | ".join(formatted_entries)

            table.add_row(
                Text(principal, style="bold #00FF9C"),
                Text(display_entries)
            )

        self._last_bindings_count = len(bindings)
