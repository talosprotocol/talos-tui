import pytest
from unittest.mock import AsyncMock
from talos_tui.core.coordinator import Coordinator, TuiState
from talos_tui.core.state import StateStore
from talos_tui.domain.models import VersionInfo, Health


@pytest.mark.asyncio
async def test_handshake_success() -> None:
    # Setup
    store = StateStore()
    gateway = AsyncMock()
    audit = AsyncMock()

    # Mock successful responses
    gateway.get_health.return_value = Health(status="ok")
    audit.get_health.return_value = Health(status="ok")

    gateway.get_version.return_value = VersionInfo(
        version="1.0.0",
        git_sha="abc",
        contracts_version="1.0.0",
        api_version="v1"
    )
    audit.get_version.return_value = VersionInfo(
        version="1.0.0",
        git_sha="abc",
        contracts_version="1.0.0",
        api_version="v1"
    )

    coordinator = Coordinator(
        store, gateway, audit, contracts_version_gate="1"
    )

    # Act - Simulate the handshake flow manually
    # 1. Gateway Handshake
    await coordinator._do_handshake("gateway")
    assert store.gateway.health_ok is True
    assert store.gateway.version == "1.0.0"
    assert coordinator.state == TuiState.HANDSHAKE_AUDIT

    # 2. Audit Handshake
    await coordinator._do_handshake("audit")
    assert store.audit.health_ok is True
    assert store.audit.version == "1.0.0"
    assert coordinator.state == TuiState.RUNNING  # type: ignore[comparison-overlap]


@pytest.mark.asyncio
async def test_handshake_incompatible() -> None:
    # Setup
    store = StateStore()
    gateway = AsyncMock()
    audit = AsyncMock()

    gateway.get_health.return_value = Health(status="ok")
    gateway.get_version.return_value = VersionInfo(
        version="1.0.0",
        git_sha="abc",
        contracts_version="2.0.0",
        api_version="v1"
    )

    # Coordinator expects v1, but we give v2
    coordinator = Coordinator(
        store, gateway, audit, contracts_version_gate="1"
    )

    # Act
    await coordinator._do_handshake("gateway")

    # Assert
    assert coordinator.state == TuiState.FATAL
    assert store.is_fatal is True
    assert (
        store.global_error and "Incompatible contracts" in store.global_error
    )
