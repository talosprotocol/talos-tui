import pytest
from unittest.mock import AsyncMock
from talos_tui.core.coordinator import Coordinator, TuiState
from talos_tui.core.state import StateStore
from talos_tui.domain.models import Health, VersionInfo

@pytest.mark.asyncio
async def test_handshake_success():
    store = StateStore()
    gateway = AsyncMock()
    audit = AsyncMock()

    gateway.get_health.return_value = Health(status="ok")
    gateway.get_version.return_value = VersionInfo(
        version="1.0.0", git_sha="abc", contracts_version="1.0.0", api_version="v1"
    )
    audit.get_health.return_value = Health(status="ok")
    audit.get_version.return_value = VersionInfo(
        version="1.0.0", git_sha="abc", contracts_version="1.0.0", api_version="v1"
    )

    coordinator = Coordinator(store, gateway, audit, contracts_version_gate="1")

    await coordinator._do_handshake("gateway")
    assert coordinator.state == TuiState.HANDSHAKE_AUDIT

    await coordinator._do_handshake("audit")
    assert coordinator.state == TuiState.RUNNING
    assert store.gateway.contracts_version == "1.0.0"
    assert store.audit.contracts_version == "1.0.0"

@pytest.mark.asyncio
async def test_handshake_incompatible():
    store = StateStore()
    gateway = AsyncMock()
    audit = AsyncMock()

    gateway.get_health.return_value = Health(status="ok")
    gateway.get_version.return_value = VersionInfo(
        version="1.0.0", git_sha="abc", contracts_version="2.0.0", api_version="v1"
    )
    audit.get_health.return_value = Health(status="ok")
    audit.get_version.return_value = VersionInfo(
        version="1.0.0", git_sha="abc", contracts_version="2.0.0", api_version="v1"
    )

    coordinator = Coordinator(store, gateway, audit, contracts_version_gate="1")

    await coordinator._do_handshake("gateway")

    assert coordinator.state == TuiState.FATAL
    assert store.is_fatal is True
    # The exact error storage might vary by version, check both
    assert (store.gateway.error and "Incompatible contracts" in store.gateway.error) or \
           (store.global_error and "Incompatible contracts" in store.global_error)
