from __future__ import annotations
import random
import time
from typing import Sequence, Optional, Any, Dict

from talos_tui.domain.models import (
    Health, MetricsSummary, Peer, Session, VersionInfo, AuditPage, AuditEvent,
    RbacRole, RbacBinding, RbacBindingEntry, RbacScope,
    Secret, KekStatus, RotationOperation, ConfigExport,
    GovernanceEntry, BudgetScope, Team, VirtualKey, McpServer, McpPolicy,
)


class MockGatewayAdapter:
    """Mock gateway adapter for offline / CI mode (TALOS_TUI_MOCK=1)."""

    def __init__(self) -> None:
        # Mutable in-memory state following actualized backend rules
        self._secrets: list[Secret] = [
            Secret(
                name="TALOS_API_KEY",
                kek_id="env",
                created_at="2024-03-20T10:00:00Z",
                updated_at="2024-03-20T10:00:00Z",
            ),
            Secret(
                name="anthropic-api-key",
                kek_id="kek-v1-mock",
                created_at="2024-03-21T15:30:00Z",
                updated_at="2024-03-21T15:30:00Z",
            ),
        ]
        self._active_rotation: Optional[RotationOperation] = None
        self._mcp_servers: list[McpServer] = [
            McpServer(
                id="filesystem",
                name="Filesystem",
                endpoint="stdio://filesystem",
                enabled=True,
                version=1,
            )
        ]
        self._mcp_policies: list[McpPolicy] = [
            McpPolicy(
                id="policy-test-team",
                team_id="test-team",
                allowed_servers=["filesystem"],
                allowed_tools=["*"],
            )
        ]

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
            RbacRole(
                role_id="admin",
                name="Super Administrator",
                permissions=["*"],
                built_in=True,
                description="Full platform access",
            ),
            RbacRole(
                role_id="auditor",
                name="Audit Viewer",
                permissions=["audit:read"],
                built_in=True,
                description="Read-only access",
            ),
            RbacRole(
                role_id="operator",
                name="Operator",
                permissions=["mcp:*", "ui:manage"],
                built_in=False,
                description="Standard operator",
            ),
        ]

    async def list_rbac_bindings(self) -> Sequence[RbacBinding]:
        return [
            RbacBinding(
                principal_id="admin@talos.security",
                bindings=[
                    RbacBindingEntry(
                        binding_id="b1",
                        role_id="admin",
                        scope=RbacScope(scope_type="global"),
                    )
                ],
            ),
        ]

    async def upsert_rbac_role(self, role: Dict[str, Any]) -> RbacRole:
        return RbacRole(**role)

    async def upsert_rbac_binding(self, binding: Dict[str, Any]) -> RbacBinding:
        return RbacBinding(**binding)

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
                "openai-main": {
                    "provider": "openai",
                    "endpoint": "https://api.openai.com/v1",
                    "enabled": True,
                    "version": 2,
                },
                "anthropic-backup": {
                    "provider": "anthropic",
                    "endpoint": "https://api.anthropic.com/v1",
                    "enabled": True,
                    "version": 1,
                },
            },
            model_groups={
                "gpt-4-prod": {
                    "name": "GPT-4 Production",
                    "deployments": ["openai-main"],
                    "routing_policy_id": "default",
                    "version": 3,
                },
            },
            routing_policies={
                "default": {"version": 1, "created_at": "2024-01-01T00:00:00Z"},
            }
        )

    async def apply_config(self, config: Dict[str, Any]) -> None:
        # No-op in mock
        pass

    # --- Governance ---

    async def list_governance_logs(self) -> Sequence[GovernanceEntry]:
        return [
            GovernanceEntry(
                trace_id="trace-mock-1",
                sequence_number=1,
                artifact_type="policy",
                ts="2024-03-22T12:00:00Z",
                status="success",
                principal_id="dev-admin",
                artifact_id="policy-test-team",
            )
        ]

    async def telemetry_stats(self, window_hours: int = 24) -> Dict[str, Any]:
        return {
            "requests_total": random.randint(100, 1000),
            "auth_success_rate": 0.98,
            "latency_avg_ms": 25.0,
            "latency_p50_ms": 15.0,
            "latency_p95_ms": 85.0
        }

    async def audit_stats(self, window_hours: int = 24) -> Dict[str, Any]:
        return {
            "requests_24h": 1000,
            "auth_success_rate": 0.95,
            "denial_reason_counts": {"INVALID_CAPABILITY": 5, "RATE_LIMIT": 10}
        }

    # --- Budgets and Keys ---

    async def list_budget_scopes(self) -> Sequence[BudgetScope]:
        return [
            BudgetScope(
                id="scope-test-team",
                scope_type="team",
                scope_id="test-team",
                period_start="2024-03-01T00:00:00Z",
                limit_usd=100.0,
                used_usd=12.5,
                reserved_usd=1.25,
                overdraft_usd=0.0,
            )
        ]

    async def list_virtual_keys(self) -> Sequence[VirtualKey]:
        return [
            VirtualKey(
                id="vk-test",
                team_id="test-team",
                scopes=["llm.invoke", "mcp.invoke"],
                allowed_model_groups=["ollama-group"],
                budget_mode="enforce",
            )
        ]

    async def list_teams(self) -> Sequence[Team]:
        return [
            Team(
                id="test-team",
                name="Test Team",
                budget_mode="enforce",
                overdraft_usd=0.0,
            )
        ]

    # --- MCP ---

    async def list_mcp_servers(self) -> Sequence[McpServer]:
        return list(self._mcp_servers)

    async def create_mcp_server(self, server: Dict[str, Any]) -> McpServer:
        created = McpServer(**{**server, "version": 1})
        self._mcp_servers = [item for item in self._mcp_servers if item.id != created.id]
        self._mcp_servers.append(created)
        return created

    async def enable_mcp_server(self, server_id: str) -> McpServer:
        return self._set_mcp_server_enabled(server_id, True)

    async def disable_mcp_server(self, server_id: str) -> McpServer:
        return self._set_mcp_server_enabled(server_id, False)

    async def delete_mcp_server(self, server_id: str) -> None:
        self._mcp_servers = [item for item in self._mcp_servers if item.id != server_id]

    async def list_mcp_policies(self, team_id: Optional[str] = None) -> Sequence[McpPolicy]:
        if team_id:
            return [item for item in self._mcp_policies if item.team_id == team_id]
        return list(self._mcp_policies)

    async def upsert_mcp_policy(self, policy: Dict[str, Any]) -> McpPolicy:
        updated = McpPolicy(**policy)
        self._mcp_policies = [item for item in self._mcp_policies if item.id != updated.id]
        self._mcp_policies.append(updated)
        return updated

    async def delete_mcp_policy(self, policy_id: str) -> None:
        self._mcp_policies = [item for item in self._mcp_policies if item.id != policy_id]

    def _set_mcp_server_enabled(self, server_id: str, enabled: bool) -> McpServer:
        for index, server in enumerate(self._mcp_servers):
            if server.id == server_id:
                updated = server.model_copy(
                    update={"enabled": enabled, "version": server.version + 1}
                )
                self._mcp_servers[index] = updated
                return updated
        raise KeyError(server_id)


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
        proof_states = ["VERIFIED", "VERIFIED", "FAILED", "MISSING_INPUTS", "UNVERIFIED"]
        
        for i in range(count):
            outcome = random.choice(outcomes)
            proof_state = random.choice(proof_states)
            reason = "CURSOR_MISMATCH" if proof_state == "FAILED" and random.random() > 0.5 else None
            
            items.append(AuditEvent(
                event_id=f"evt-{random.randint(10000, 99999)}",
                ts=str(int(time.time())),
                outcome=outcome,
                tool=random.choice(tools),
                agent_id=f"agent-{random.randint(1, 5)}",
                integrity={
                    "proof_state": proof_state,
                    "failure_reason": reason,
                }
            ))

        return AuditPage(
            items=items,
            next_cursor="mock_cursor",
            has_more=True
        )
