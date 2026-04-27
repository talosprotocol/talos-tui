from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from talos_tui.app import TalosTuiApp
from talos_tui.core.coordinator import TuiState
from talos_tui.core.state import StateStore
from talos_tui.ui.screens.api_console import ApiConsole
from talos_tui.ui.screens.secrets import SecretsManager


class ApiConsoleHarness(ApiConsole):
    def __init__(self) -> None:
        super().__init__()
        self._test_app: object | None = None

    @property
    def app(self) -> object:
        assert self._test_app is not None
        return self._test_app


class SecretsManagerHarness(SecretsManager):
    def __init__(self, store: StateStore) -> None:
        super().__init__(store)
        self._test_app: object | None = None

    @property
    def app(self) -> object:
        assert self._test_app is not None
        return self._test_app


def test_app_exposes_api_console_binding_and_screen_action() -> None:
    app = TalosTuiApp()
    app.coordinator = SimpleNamespace(state=TuiState.RUNNING)
    app.switch_screen = MagicMock()  # type: ignore[method-assign]

    bindings = {binding.action: binding.key for binding in app.BINDINGS}

    assert bindings["show_api_console"] == "x"

    app.action_show_api_console()

    app.switch_screen.assert_called_once_with("api-console")


def test_app_exposes_mcp_binding_and_screen_action() -> None:
    app = TalosTuiApp()
    app.coordinator = SimpleNamespace(state=TuiState.RUNNING)
    app.switch_screen = MagicMock()  # type: ignore[method-assign]

    bindings = {binding.action: binding.key for binding in app.BINDINGS}

    assert bindings["show_mcp"] == "m"

    app.action_show_mcp()

    app.switch_screen.assert_called_once_with("mcp")


@pytest.mark.asyncio
async def test_api_console_validation_errors_surface_in_ui() -> None:
    screen = ApiConsoleHarness()
    screen._test_app = SimpleNamespace(gateway=AsyncMock(), audit=AsyncMock())
    screen.notify = MagicMock()  # type: ignore[method-assign]

    primary_arg = SimpleNamespace(value="")
    secondary_arg = SimpleNamespace(value="")
    payload = SimpleNamespace(value='{"value": "sk-test"}')
    last_operation = MagicMock()
    response = MagicMock()
    widgets = {
        "#api-primary-arg": primary_arg,
        "#api-secondary-arg": secondary_arg,
        "#api-payload": payload,
        "#api-last-operation": last_operation,
        "#api-response": response,
    }
    screen.query_one = MagicMock(side_effect=lambda selector, *_args: widgets[selector])  # type: ignore[method-assign]

    event = SimpleNamespace(button=SimpleNamespace(id="op-gateway_create_secret"))

    await screen.run_operation(event)

    response.update.assert_called_once()
    rendered_error = response.update.call_args.args[0]
    assert "Primary arg must contain the secret name." in rendered_error
    screen.notify.assert_called_once()


@pytest.mark.asyncio
async def test_secrets_rotation_completion_reenables_button_and_stops_polling() -> None:
    store = StateStore()
    screen = SecretsManagerHarness(store)
    gateway = AsyncMock()
    gateway.get_rotation_status.return_value = SimpleNamespace(
        status="completed",
        stats={"scanned": 4, "rotated": 4, "failed": 0},
        last_error=None,
        model_dump=lambda: {"id": "rotate-123", "status": "completed", "stats": {"scanned": 4, "rotated": 4, "failed": 0}},
    )
    screen._test_app = SimpleNamespace(gateway=gateway)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    screen._update_rotation_panel = MagicMock()  # type: ignore[method-assign]
    screen._rotation_op_id = "rotate-123"
    poll_timer = MagicMock()
    screen._rotation_poll_timer = poll_timer

    rotate_button = MagicMock()
    screen.query_one = MagicMock(return_value=rotate_button)  # type: ignore[method-assign]

    await screen._poll_rotation()

    assert screen._rotation_op_id is None
    assert rotate_button.disabled is False
    assert rotate_button.label == "↺  Rotate All Secrets"
    poll_timer.stop.assert_called_once()
    screen.notify.assert_called_once()


@pytest.mark.asyncio
async def test_secrets_add_secret_uses_gateway_and_clears_form() -> None:
    screen = SecretsManagerHarness(StateStore())
    gateway = AsyncMock()
    screen._test_app = SimpleNamespace(gateway=gateway)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    screen._refresh_from_gateway = AsyncMock()  # type: ignore[method-assign]

    name_input = SimpleNamespace(value="openai-key")
    value_input = SimpleNamespace(value="sk-test")
    add_button = SimpleNamespace(disabled=False, label="Add Secret")
    widgets = {
        "#secret-name": name_input,
        "#secret-value": value_input,
        "#btn-add-secret": add_button,
    }
    screen.query_one = MagicMock(side_effect=lambda selector, *_args: widgets[selector])  # type: ignore[method-assign]

    await screen.action_add_secret()

    gateway.create_secret.assert_awaited_once_with("openai-key", "sk-test")
    screen._refresh_from_gateway.assert_awaited_once_with(gateway)
    assert name_input.value == ""
    assert value_input.value == ""
    assert add_button.disabled is False
    assert add_button.label == "Add Secret"
    screen.notify.assert_called_once()


@pytest.mark.asyncio
async def test_secrets_delete_selected_uses_gateway_for_cursor_row() -> None:
    store = StateStore()
    store.secrets = [
        {"name": "openai-key", "kek_id": "kek-v1"},
        {"name": "anthropic-key", "kek_id": "kek-v1"},
    ]
    screen = SecretsManagerHarness(store)
    gateway = AsyncMock()
    screen._test_app = SimpleNamespace(gateway=gateway)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    screen._refresh_from_gateway = AsyncMock()  # type: ignore[method-assign]

    delete_button = SimpleNamespace(disabled=False, label="Delete Selected")
    table = SimpleNamespace(cursor_row=1)
    widgets = {
        "#btn-delete-secret": delete_button,
        "#secrets-table": table,
    }
    screen.query_one = MagicMock(side_effect=lambda selector, *_args: widgets[selector])  # type: ignore[method-assign]

    await screen.action_delete_selected()

    gateway.delete_secret.assert_awaited_once_with("anthropic-key")
    screen._refresh_from_gateway.assert_awaited_once_with(gateway)
    assert delete_button.disabled is False
    assert delete_button.label == "Delete Selected"
    screen.notify.assert_called_once()
