"""HTTP Adapter for Gateway Service."""
from __future__ import annotations

import logging
from typing import Sequence, Optional, Any, Dict
import aiohttp
from ..domain.models import (
    Health, MetricsSummary, Peer, Session, VersionInfo,
    RbacRole, RbacBinding, Secret, KekStatus, RotationOperation, ConfigExport, GovernanceEntry,
    BudgetScope, Team, VirtualKey, McpServer, McpPolicy
)
from .base import BaseHttpAdapter
from .token_broker import AsyncScopedJwtTokenBroker


logger = logging.getLogger(__name__)


class HttpGatewayAdapter(BaseHttpAdapter):
    """Adapter for interacting with the Gateway Service via HTTP."""

    def __init__(
        self,
        base_url: str,
        session: aiohttp.ClientSession,
        validator: Optional[Any] = None,
        version: str = "0.1.0",
        auth_broker: Optional[AsyncScopedJwtTokenBroker] = None,
        auth_permissions: Optional[Sequence[str]] = None,
        **kwargs: Any
    ):
        super().__init__(
            base_url,
            session,
            auth_broker=auth_broker,
            auth_permissions=auth_permissions,
            **kwargs,
        )
        self.validator = validator
        self.headers = {"User-Agent": f"talos-tui/{version}"}

    async def get_version(self) -> VersionInfo:
        """Get service version information."""

        data = await self._request("GET", "version")
        # Optional: validator.validate("common/version.schema.json", data)
        return VersionInfo(**data)

    async def get_health(self) -> Health:
        """Get service health status."""

        # Gateway health check at /health/ready
        data = await self._request("GET", "health/ready")
        return Health(**data)

    async def get_metrics_summary(self) -> MetricsSummary:
        """retrieve metrics summary."""

        data = await self._request("GET", "metrics/summary")
        # In multi-region, 403 or 404 might happen if not registered
        return MetricsSummary(**data)

    async def list_peers(self) -> Sequence[Peer]:
        """List connected peers."""

        data = await self._request("GET", "peers")
        items = data.get("peers") if "peers" in data else data
        if not isinstance(items, list):
            return []
        return [Peer(**p) for p in items[:500]]

    async def list_sessions(self) -> Sequence[Session]:
        """List active sessions."""

        data = await self._request("GET", "sessions")
        items = data.get("sessions") if "sessions" in data else data
        if not isinstance(items, list):
            return []
        return [Session(**s) for s in items[:500]]

    async def list_rbac_roles(self) -> Sequence[RbacRole]:
        """List current authority roles."""
        data = await self._request("GET", "admin/v1/rbac/roles")
        items = data.get("roles", [])
        return [RbacRole(**r) for r in items]

    async def list_rbac_bindings(self) -> Sequence[RbacBinding]:
        """List active access bindings."""
        data = await self._request("GET", "admin/v1/rbac/bindings")
        items = data.get("bindings", [])
        return [RbacBinding(**b) for b in items]

    # Secrets Management
    async def list_secrets(self) -> Sequence[Secret]:
        """List all secrets metadata."""
        data = await self._request("GET", "admin/v1/secrets")
        items = data.get("secrets", [])
        return [Secret(**s) for s in items]

    async def create_secret(self, name: str, value: str) -> None:
        """Create a new secret."""
        await self._request("POST", "admin/v1/secrets", json={"name": name, "value": value})

    async def delete_secret(self, name: str) -> None:
        """Delete a secret."""
        await self._request("DELETE", f"admin/v1/secrets/{name}")

    async def get_kek_status(self) -> KekStatus:
        """Get current KEK provider status."""
        data = await self._request("GET", "admin/v1/secrets/kek-status")
        return KekStatus(**data)

    async def rotate_all_secrets(self) -> RotationOperation:
        """Trigger global secret rotation."""
        data = await self._request("POST", "admin/v1/secrets/rotate-all", json={})
        return RotationOperation(**data)

    async def get_rotation_status(self, op_id: str) -> RotationOperation:
        """Get status of a rotation operation."""
        data = await self._request("GET", f"admin/v1/secrets/rotation-status/{op_id}")
        return RotationOperation(**data)

    # Config Management
    async def export_config(self) -> ConfigExport:
        """Export current platform configuration."""
        data = await self._request("GET", "admin/v1/config:export")
        return ConfigExport(**data)

    async def apply_config(self, config: Dict[str, Any]) -> None:
        """Apply a new platform configuration."""
        await self._request("POST", "admin/v1/config:apply", json=config)

    async def list_governance_logs(self) -> Sequence[GovernanceEntry]:
        """List high-integrity governance execution logs."""
        data = await self._request("GET", "admin/v1/governance/logs")
        items = data.get("entries", [])
        return [GovernanceEntry(**e) for e in items]

    # Budget & Key Management
    async def list_budget_scopes(self) -> Sequence[BudgetScope]:
        """List current budget scopes and usage."""
        data = await self._request("GET", "admin/v1/budgets/scopes")
        items = data.get("scopes", [])
        return [BudgetScope(**s) for s in items]

    async def list_virtual_keys(self) -> Sequence[VirtualKey]:
        """List all virtual keys metadata."""
        data = await self._request("GET", "admin/v1/keys")
        items = data.get("keys", [])
        return [VirtualKey(**k) for k in items]

    async def list_teams(self) -> Sequence[Team]:
        """List all teams configuration."""
        data = await self._request("GET", "admin/v1/teams")
        items = data.get("teams", [])
        return [Team(**t) for t in items]

    async def list_mcp_servers(self) -> Sequence[McpServer]:
        """List all MCP servers."""
        data = await self._request("GET", "admin/v1/mcp/servers")
        items = data.get("servers", [])
        return [McpServer(**s) for s in items]

    async def list_mcp_policies(self, team_id: Optional[str] = None) -> Sequence[McpPolicy]:
        """List MCP policies, optionally filtered by team."""
        params = {"team_id": team_id} if team_id else {}
        data = await self._request("GET", "admin/v1/mcp/policies", params=params)
        items = data.get("policies", [])
        return [McpPolicy(**p) for p in items]
