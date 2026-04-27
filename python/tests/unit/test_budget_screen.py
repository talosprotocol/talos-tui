from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from talos_tui.core.state import StateStore
from talos_tui.ui.screens.budgets import BudgetManager


class BudgetManagerHarness(BudgetManager):
    def __init__(self, store: StateStore) -> None:
        super().__init__(store)
        self._test_app: object | None = None

    @property
    def app(self) -> object:
        assert self._test_app is not None
        return self._test_app


@pytest.mark.asyncio
async def test_budget_refresh_data_loads_gateway_snapshots() -> None:
    store = StateStore()
    screen = BudgetManagerHarness(store)
    gateway = AsyncMock()
    gateway.list_budget_scopes.return_value = [
        SimpleNamespace(model_dump=lambda: {"scope_id": "platform", "limit_usd": 100})
    ]
    gateway.list_virtual_keys.return_value = [
        SimpleNamespace(model_dump=lambda: {"id": "vk_123", "team_id": "eng"})
    ]
    gateway.list_teams.return_value = [
        SimpleNamespace(model_dump=lambda: {"id": "eng", "name": "Engineering"})
    ]
    screen._test_app = SimpleNamespace(gateway=gateway)
    screen.notify = MagicMock()  # type: ignore[method-assign]
    screen.update_view = MagicMock()  # type: ignore[method-assign]

    await screen.action_refresh_data()

    gateway.list_budget_scopes.assert_awaited_once()
    gateway.list_virtual_keys.assert_awaited_once()
    gateway.list_teams.assert_awaited_once()
    assert store.budget_scopes == [{"scope_id": "platform", "limit_usd": 100}]
    assert store.virtual_keys == [{"id": "vk_123", "team_id": "eng"}]
    assert store.teams == [{"id": "eng", "name": "Engineering"}]
    screen.update_view.assert_called_once()
    screen.notify.assert_called_once()
