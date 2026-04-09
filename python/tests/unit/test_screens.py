from unittest.mock import MagicMock
from talos_tui.ui.screens.dashboard import StatusDashboard
from talos_tui.ui.screens.audit import AuditViewer
from talos_tui.core.state import StateStore


def test_dashboard_update_metrics() -> None:
    store = StateStore()
    dash = StatusDashboard(store)

    # Mock query_one to return a mock widget that accepts update_value
    mock_widget = MagicMock()
    dash.query_one = MagicMock(return_value=mock_widget)  # type: ignore[method-assign]

    # Update store directly
    store.metrics = {
        "connected_peers": 10,
        "active_sessions": 5,
        "latency_p50_ms": 12.5,
        "latency_p95_ms": 40.2
    }

    dash.refresh_view()

    # Verify calls
    queried_ids = [call.args[0] for call in dash.query_one.call_args_list]
    assert "#peers" in queried_ids
    assert "#sessions" in queried_ids
    assert "#p50" in queried_ids
    assert "#p95" in queried_ids


def test_audit_refresh_view() -> None:
    store = StateStore()
    audit = AuditViewer(store)
    mock_table = MagicMock()
    audit.query_one = MagicMock(return_value=mock_table)  # type: ignore[method-assign]

    # Setup store events
    store.audit_events = [
        {"event_id": "1", "ts": "2023", "schema_id": "login", "outcome": "OK", "payload": {}}
    ]

    audit.refresh_view()

    # Verify add_row called (args: severity, timestamp, type, id)
    # Severity I for OK
    # Timestamp: 2023
    # Type: login (OK)
    # ID: 1
    call_args = mock_table.add_row.call_args[0]
    # We check string contents implicitly since they are Rich Text objects
    assert "2023" in str(call_args[1])
    assert "login" in str(call_args[2])
    assert "1" in str(call_args[3])


def test_startup_screen_buttons() -> None:
    from talos_tui.ui.screens.startup import StartupScreen
    from typing import Any

    class TestableStartupScreen(StartupScreen):
        def __init__(self, store: StateStore):
            super().__init__(store)
            self._test_app: Any = None

        @property
        def app(self) -> Any:
            return self._test_app

    store = StateStore()
    screen = TestableStartupScreen(store)

    # Mock query_one so self.query_one("#loading") works
    mock_loading = MagicMock()
    screen.query_one = MagicMock(return_value=mock_loading)  # type: ignore[method-assign]
    
    mock_app = MagicMock()
    mock_coordinator = MagicMock()
    mock_app.coordinator = mock_coordinator
    screen._test_app = mock_app
    
    # Test Quit
    quit_event = MagicMock()
    quit_event.button.id = "quit-btn"
    screen.on_button_pressed(quit_event)
    mock_app.exit.assert_called_once()
    
    # Test Retry
    retry_event = MagicMock()
    retry_event.button.id = "retry-btn"
    screen.on_button_pressed(retry_event)
    mock_coordinator.retry.assert_called_once()
