from __future__ import annotations
import random
import time
from typing import Sequence, Optional, Any, Dict

from talos_tui.domain.models import (
    Health, MetricsSummary, Peer, Session, VersionInfo, AuditPage, AuditEvent,
    RbacRole, RbacBinding, RbacBindingEntry, RbacScope,
    Secret, KekStatus, RotationOperation, ConfigExport,
)


class MockGatewayAdapter:
    """Mock gateway adapter for offline / CI mode (TALOS_TUI_MOCK=1)."""

    def __init__(self) -> None:
        # Mutable in-memory state following actualized backend rules
        self._secrets: list[Secret] = [
            Secret(name="TALOS_API_KEY", kek_id="env", created_at="2024-03-20T10:00:00Z", updated_at="2024-03-20T10:00:00Z"),
            Secret(name="anthropic-api-key", kek_id="kek-v1-mock", created_at="2024-03-21T15:30:00Z", updated_at="2024-03-21T15:30:00Z"),
        ]
        self._active_rotation: Optional[RotationOperation] = None

    async def get_version(self) -> VersionInfo:
        return VersionInfo(
            version="1.2.3-mock",
            git_sha="deadbeef",
            contracts_version="1.0.0",
            api_version="v1"
        )

    async def get_health(self) -> Health:
        return Health(status="ok", detail="Running in Mock Mode")

    async def get_metrics_summary(self) -> MetricsSummary:
        return MetricsSummary(
            latency_p50_ms=random.uniform(5.0, 50.0),
            latency_p95_ms=random.uniform(50.0, 150.0),
            connected_peers=random.randint(10, 50),
            active_sessions=random.randint(1, 10)
        )

    async def list_peers(self) -> Sequence[Peer]:
        return [
            Peer(peer_id=f"peer-{i}", services=["gateway"]) for i in range(5)
        ]

    async def list_sessions(self) -> Sequence[Session]:
        return [Session(session_id=f"sess-{i}") for i in range(3)]

    # --- RBAC ---

    async def list_rbac_roles(self) -> Sequence[RbacRole]:
        return [
            RbacRole(role_id="admin", name="Super Administrator", permissions=["*"], built_in=True, description="Full platform access"),
            RbacRole(role_id="auditor", name="Audit Viewer", permissions=["audit:read"], built_in=True, description="Read-only access"),
            RbacRole(role_id="operator", name="Operator", permissions=["mcp:*", "ui:manage"], built_in=False, description="Standard operator"),
        ]

    async def list_rbac_bindings(self) -> Sequence[RbacBinding]:
        return [
            RbacBinding(principal_id="admin@talos.security", bindings=[
                RbacBindingEntry(binding_id="b1", role_id="admin", scope=RbacScope(scope_type="global"))
            ]),
        ]

    # --- Secrets ---

    async def list_secrets(self) -> Sequence[Secret]:
        return list(self._secrets)

    async def create_secret(self, name: str, value: str) -> None:
        self._secrets.append(Secret(name=name, kek_id="kek-v1-mock"))

    async def delete_secret(self, name: str) -> None:
        self._secrets = [s for s in self._secrets if s.name != name]

    async def get_kek_status(self) -> KekStatus:
        stale = sum(1 for s in self._secrets if s.kek_id != "kek-v1-mock")
        return KekStatus(
            current_kek_id="kek-v1-mock",
            loaded_kek_ids=["kek-v1-mock", "kek-v0-legacy"],
            stale_counts={"kek-v0-legacy": stale}
        )

    async def rotate_all_secrets(self) -> RotationOperation:
        # Simulate re-encrypting stale secrets
        stale = [s for s in self._secrets if s.kek_id != "kek-v1-mock"]
        for s in stale:
            s.kek_id = "kek-v1-mock"
        op_id = f"op-mock-{int(time.time())}"
        return RotationOperation(
            id=op_id,
            status="completed",
            target_kek_id="kek-v1-mock",
            stats={"scanned": len(self._secrets), "rotated": len(stale), "failed": 0},
            started_at=str(time.time()),
        )

    async def get_rotation_status(self, op_id: str) -> RotationOperation:
        return RotationOperation(
            id=op_id,
            status="completed",
            target_kek_id="kek-v1-mock",
            stats={"scanned": len(self._secrets), "rotated": len(self._secrets), "failed": 0},
            started_at=str(time.time()),
        )

    # --- Config ---

    async def export_config(self) -> ConfigExport:
        return ConfigExport(
            upstreams={
                "openai-main": {"provider": "openai", "endpoint": "https://api.openai.com/v1", "enabled": True, "version": 2},
                "anthropic-backup": {"provider": "anthropic", "endpoint": "https://api.anthropic.com/v1", "enabled": True, "version": 1},
            },
            model_groups={
                "gpt-4-prod": {"name": "GPT-4 Production", "deployments": ["openai-main"], "routing_policy_id": "default", "version": 3},
            },
            routing_policies={
                "default": {"version": 1, "created_at": "2024-01-01T00:00:00Z"},
            }
        )

    async def apply_config(self, config: Dict[str, Any]) -> None:
        # No-op in mock
        pass


class MockAuditAdapter:
    """Mock audit adapter for offline / CI mode."""

    async def get_version(self) -> VersionInfo:
        return VersionInfo(
            version="1.2.3-mock",
            git_sha="deadbeef",
            contracts_version="1.0.0",
            api_version="v1"
        )

    async def get_health(self) -> Health:
        return Health(status="ok", detail="Mock Audit Adapter")

    async def list_events(
        self, limit: int, before: Optional[str]
    ) -> AuditPage:
        items = []
        count = random.randint(0, 5)
        outcomes = ["OK", "OK", "OK", "DENY", "ERROR"]
        tools = ["read_file", "bash", "search_web", "", "mcp.list_tools"]
        for i in range(count):
            outcome = random.choice(outcomes)
            items.append(AuditEvent(
                event_id=f"evt-{random.randint(10000, 99999)}",
                ts=str(int(time.time())),
                outcome=outcome,
                tool=random.choice(tools),
                agent_id=f"agent-{random.randint(1, 5)}",
            ))

        return AuditPage(
            items=items,
            next_cursor="mock_cursor",
            has_more=True
        )
