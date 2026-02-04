import pytest
from unittest.mock import MagicMock, AsyncMock

from talos_tui.core.state import StateStore, HealthUpdated, ErrorOccurred # type: ignore[import-not-found, import-untyped]
from talos_tui.core.coordinator import Coordinator, TuiState # type: ignore[import-not-found, import-untyped]
from talos_tui.ports.errors import TuiError # type: ignore[import-not-found, import-untyped]

class TestStateStore:
    def test_health_update_reducer(self) -> None:
        store = StateStore()
        event = HealthUpdated(source="gateway", is_ok=True, status_msg="READY")
        store.reduce(event)
        
        assert store.gateway.health_ok is True
        assert store.gateway.status_msg == "READY"
        assert store.gateway.last_updated_at > 0

    def test_fatal_error_reducer(self) -> None:
        store = StateStore()
        event = ErrorOccurred(source="audit", kind="AUTH", message="403 Forbidden", is_fatal=True)
        store.reduce(event)
        
        # Reducer prefixes fatal errors
        assert store.audit.error and "403 Forbidden" in store.audit.error
        assert store.is_fatal is True
        assert store.global_error and "403 Forbidden" in store.global_error

@pytest.mark.asyncio
class TestCoordinator:
    async def test_max_attempts_leads_to_fatal(self) -> None:
        store = StateStore()
        gateway = MagicMock()
        audit = MagicMock()
        
        # Mock a transient failure forever for gateway health
        gateway.get_health = AsyncMock(side_effect=TuiError(kind="NETWORK", message="500 Internal"))
        
        coord = Coordinator(store, gateway, audit, max_handshake_attempts=2, contracts_version_gate="1")
        
        # Attempt 1 -> Fail
        await coord._do_handshake("gateway")
        assert coord._handshake_attempts["gateway"] == 1
        
        # Attempt 2 -> Fail
        await coord._do_handshake("gateway")
        assert coord._handshake_attempts["gateway"] == 2
        
        # Attempt 3 -> Triggers "Max attempts exceeded" check at start
        await coord._do_handshake("gateway")
        assert coord.state == TuiState.FATAL
        assert store.gateway.error and "Max attempts" in store.gateway.error

    async def test_auth_failure_leads_to_fatal_instantly(self) -> None:
        store = StateStore()
        gateway = MagicMock()
        audit = MagicMock()
        
        gateway.get_health = AsyncMock(side_effect=TuiError(kind="AUTH", message="401 Unauthorized"))
        
        coord = Coordinator(store, gateway, audit)
        await coord._do_handshake("gateway")
        
        assert coord.state == TuiState.FATAL
        assert store.is_fatal is True
        assert store.gateway.error == "401 Unauthorized"
