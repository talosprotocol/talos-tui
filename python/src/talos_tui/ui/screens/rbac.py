"""Module for the RBAC management screen in the Talos TUI."""
from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label, TabbedContent, TabPane, Input, Button, Static
from textual.containers import Container, Horizontal, Vertical
from rich.text import Text

from talos_tui.core.state import StateStore


class RbacManager(Screen[None]):
    """Screen for managing RBAC roles and bindings."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("f5", "refresh_view", "Refresh"),
    ]

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
                    with Vertical(classes="rbac-form-panel"):
                        yield Static("[bold cyan]CREATE ROLE[/bold cyan]", classes="panel-title")
                        with Horizontal(classes="mcp-form-row"):
                            yield Input(placeholder="Role ID", id="role-id")
                            yield Input(placeholder="Name", id="role-name")
                            yield Input(placeholder="Permissions (comma separated)", id="role-perms")
                        with Horizontal(classes="mcp-actions"):
                            yield Button("Add Role", id="btn-add-role", variant="primary")
                            yield Button("Delete Selected", id="btn-delete-role", variant="error")
                    yield DataTable(id="table_roles", cursor_type="row", zebra_stripes=True)
                
                with TabPane("Bindings", id="tab_bindings"):
                    with Vertical(classes="rbac-form-panel"):
                        yield Static("[bold cyan]BIND PRINCIPAL[/bold cyan]", classes="panel-title")
                        with Horizontal(classes="mcp-form-row"):
                            yield Input(placeholder="Principal DID", id="bind-principal")
                            yield Input(placeholder="Role ID", id="bind-role")
                        with Horizontal(classes="mcp-actions"):
                            yield Button("Add Binding", id="btn-add-binding", variant="primary")
                            yield Button("Delete Selected", id="btn-delete-binding", variant="error")
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
                Text(built_in, style="#7AA2F7" if built_in == "YES" else ""),
                key=role_id
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
                Text(display_entries),
                key=principal
            )

        self._last_bindings_count = len(bindings)

    @on(Button.Pressed, "#btn-add-role")
    async def handle_add_role(self) -> None:
        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        rid = self.query_one("#role-id", Input).value.strip()
        name = self.query_one("#role-name", Input).value.strip()
        perms = [p.strip() for p in self.query_one("#role-perms", Input).value.split(",") if p.strip()]

        if not rid or not name:
            self.notify("Enter Role ID and Name", severity="warning")
            return

        try:
            await adapter._request("POST", "admin/v1/rbac/roles", json_data={
                "role_id": rid, "name": name, "permissions": perms
            })
            self.notify(f"Created role {rid}")
            self.query_one("#role-id", Input).value = ""
            self.query_one("#role-name", Input).value = ""
            self.query_one("#role-perms", Input).value = ""
            # Force refresh would happen via coordinator
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-delete-role")
    async def handle_delete_role(self) -> None:
        table = self.query_one("#table_roles", DataTable)
        if table.cursor_row < 0: return
        role_id = table.get_row_at(table.cursor_row)[0].plain
        
        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        try:
            await adapter._request("DELETE", f"admin/v1/rbac/roles/{role_id}")
            self.notify(f"Deleted role {role_id}")
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-add-binding")
    async def handle_add_binding(self) -> None:
        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        principal = self.query_one("#bind-principal", Input).value.strip()
        role_id = self.query_one("#bind-role", Input).value.strip()

        if not principal or not role_id:
            self.notify("Enter Principal DID and Role ID", severity="warning")
            return

        try:
            await adapter._request("POST", "admin/v1/rbac/bindings", json_data={
                "principal_id": principal,
                "bindings": [{"role_id": role_id, "scope": {"scope_type": "global"}}]
            })
            self.notify(f"Bound {principal} to {role_id}")
            self.query_one("#bind-principal", Input).value = ""
            self.query_one("#bind-role", Input).value = ""
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")

    @on(Button.Pressed, "#btn-delete-binding")
    async def handle_delete_binding(self) -> None:
        table = self.query_one("#table_bindings", DataTable)
        if table.cursor_row < 0: return
        principal = table.get_row_at(table.cursor_row)[0].plain
        
        adapter = getattr(self.app, "gateway", None)
        if not adapter: return

        try:
            await adapter._request("DELETE", f"admin/v1/rbac/bindings/{principal}")
            self.notify(f"Deleted binding for {principal}")
        except Exception as e:
            self.notify(f"Failed: {e}", severity="error")
