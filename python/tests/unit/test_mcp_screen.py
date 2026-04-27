from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from talos_tui.core.state import StateStore
from talos_tui.ui.screens.mcp import McpManager


class McpManagerHarness(McpManager):
    def __init__(self, store: StateStore) -> None:
        super().__init__(store)
        self._test_app: object | None = None

    @property
    def app(self) -> object:
        assert self._test_app is not None
        return self._test_app


def test_mcp_refresh_view_projects_servers_and_policies() -> None:
    store = StateStore()
    store.mcp_servers = [
        {
            "id": "filesystem",
            "name": "Filesystem",
            "endpoint": "stdio://filesystem",
            "enabled": True,
            "version": 2,
        }
    ]
    store.mcp_policies = [
        {
            "id": "policy-eng",
            "team_id": "engineering",
            "allowed_servers": ["filesystem", "github"],
            "enforcement_mode": "strict",
        }
    ]
    screen = McpManager(store)
    servers_table = MagicMock()
    policies_table = MagicMock()
    widgets = {
        "#mcp-servers-table": servers_table,
        "#mcp-policies-table": policies_table,
    }
    screen.query_one = MagicMock(side_effect=lambda selector, *_args: widgets[selector])  # type: ignore[method-assign]

    screen.update_view()

    server_row = servers_table.add_row.call_args.args
    policy_row = policies_table.add_row.call_args.args
    assert "filesystem" in str(server_row[0])
    assert "engineering" in str(policy_row[1])
    assert "github" in str(policy_row[2])


@pytest.mark.asyncio
async def test_mcp_refresh_data_loads_gateway_snapshots() -> None:
    store = StateStore()
    screen = McpManagerHarness(store)
    gateway = AsyncMock()
    gateway.list_mcp_servers.return_value = [
        SimpleNamespace(model_dump=lambda: {"id": "filesystem", "enabled": True})
    ]
    gateway.list_mcp_policies.return_value = [
        SimpleNamespace(model_dump=lambda: {"id": "policy-eng", "team_id": "engineering"})
    ]
    screen._test_app = SimpleNamespace(gateway=gateway)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    screen.update_view = MagicMock()  # type: ignore[method-assign]

    await screen.action_refresh_data()

    gateway.list_mcp_servers.assert_awaited_once()
    gateway.list_mcp_policies.assert_awaited_once()
    assert store.mcp_servers == [{"id": "filesystem", "enabled": True}]
    assert store.mcp_policies == [{"id": "policy-eng", "team_id": "engineering"}]
    screen.update_view.assert_called_once()
    screen.notify.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_add_server_uses_gateway_and_clears_form() -> None:
    store = StateStore()
    screen = McpManagerHarness(store)
    gateway = AsyncMock()
    screen._test_app = SimpleNamespace(gateway=gateway)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    screen._refresh_from_gateway = AsyncMock()  # type: ignore[method-assign]

    server_id = SimpleNamespace(value="filesystem")
    server_name = SimpleNamespace(value="Filesystem")
    endpoint = SimpleNamespace(value="stdio://filesystem")
    add_button = SimpleNamespace(disabled=False)
    widgets = {
        "#mcp-server-id": server_id,
        "#mcp-server-name": server_name,
        "#mcp-server-endpoint": endpoint,
        "#btn-mcp-add-server": add_button,
    }
    screen.query_one = MagicMock(side_effect=lambda selector, *_args: widgets[selector])  # type: ignore[method-assign]

    await screen.action_add_server()

    gateway.create_mcp_server.assert_awaited_once_with(
        {
            "id": "filesystem",
            "name": "Filesystem",
            "endpoint": "stdio://filesystem",
            "transport": "http",
            "enabled": True,
        }
    )
    screen._refresh_from_gateway.assert_awaited_once_with(gateway)
    assert server_id.value == ""
    assert server_name.value == ""
    assert endpoint.value == ""
    assert add_button.disabled is False
    screen.notify.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_enable_selected_uses_gateway_for_cursor_row() -> None:
    store = StateStore()
    store.mcp_servers = [
        {"id": "filesystem", "enabled": False},
        {"id": "github", "enabled": False},
    ]
    screen = McpManagerHarness(store)
    gateway = AsyncMock()
    screen._test_app = SimpleNamespace(gateway=gateway)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    screen._refresh_from_gateway = AsyncMock()  # type: ignore[method-assign]

    table = SimpleNamespace(cursor_row=1)
    screen.query_one = MagicMock(return_value=table)  # type: ignore[method-assign]

    await screen.action_enable_selected()

    gateway.enable_mcp_server.assert_awaited_once_with("github")
    screen._refresh_from_gateway.assert_awaited_once_with(gateway)
    screen.notify.assert_called_once()
