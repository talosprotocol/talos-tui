from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from talos_tui.core.state import StateStore
from talos_tui.ui.screens.config import ConfigManager


class ConfigManagerHarness(ConfigManager):
    def __init__(self, store: StateStore) -> None:
        super().__init__(store)
        self._test_app: object | None = None

    @property
    def app(self) -> object:
        assert self._test_app is not None
        return self._test_app


def test_config_export_writes_json_snapshot(tmp_path: Path, monkeypatch) -> None:
    store = StateStore()
    store.platform_config = {
        "upstreams": {
            "openai-main": {
                "provider": "openai",
                "endpoint": "https://api.openai.com/v1",
                "enabled": True,
                "version": 3,
            }
        },
        "model_groups": {},
        "routing_policies": {},
        "mcp_servers": {},
    }
    screen = ConfigManager(store)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    monkeypatch.chdir(tmp_path)

    screen.action_export_json()

    exports = list(tmp_path.glob("talos-config-*.json"))
    assert len(exports) == 1
    assert json.loads(exports[0].read_text()) == store.platform_config
    screen.notify.assert_called_once()


def test_config_export_without_loaded_data_notifies_warning() -> None:
    screen = ConfigManager(StateStore())
    screen.notify = MagicMock()  # type: ignore[method-assign]

    screen.action_export_json()

    screen.notify.assert_called_once_with("No config loaded yet.", severity="warning")


@pytest.mark.asyncio
async def test_config_refresh_data_loads_gateway_export() -> None:
    store = StateStore()
    screen = ConfigManagerHarness(store)
    gateway = AsyncMock()
    gateway.export_config.return_value = SimpleNamespace(
        model_dump=lambda: {
            "upstreams": {"openai-main": {"enabled": True}},
            "model_groups": {},
            "routing_policies": {},
            "mcp_servers": {},
        }
    )
    screen._test_app = SimpleNamespace(gateway=gateway)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    screen.update_view = MagicMock()  # type: ignore[method-assign]

    await screen.action_refresh_data()

    gateway.export_config.assert_awaited_once()
    assert store.platform_config == {
        "upstreams": {"openai-main": {"enabled": True}},
        "model_groups": {},
        "routing_policies": {},
        "mcp_servers": {},
    }
    screen.update_view.assert_called_once()
    screen.notify.assert_called_once()
