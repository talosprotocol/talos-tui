import pytest
from unittest.mock import MagicMock
from talos_tui.ui.screens.dashboard import StatusDashboard, MetricCard
from talos_tui.ui.screens.audit import AuditViewer
from talos_tui.domain.models import AuditEvent
from talos_tui.core.state import StateStore, MetricsUpdated

def test_dashboard_update_metrics():
    store = StateStore()
    dash = StatusDashboard(store)
    
    # Mock query_one to return a mock widget that accepts update_value
    mock_widget = MagicMock()
    dash.query_one = MagicMock(return_value=mock_widget)
    
    # Update store directly
    store.metrics = {
        "connected_peers": 10,
        "active_sessions": 5,
        "latency_p50_ms": 12.5,
        "latency_p95_ms": 40.2
    }
    
    dash.refresh_view()
    
    # Verify calls
    assert dash.query_one.call_count == 4
    # Check calls
    calls = dash.query_one.call_args_list
    assert calls[0][0][0] == "#peers"
    assert calls[1][0][0] == "#sessions"

def test_audit_refresh_view():
    store = StateStore()
    audit = AuditViewer(store)
    mock_table = MagicMock()
    audit.query_one = MagicMock(return_value=mock_table)
    
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
