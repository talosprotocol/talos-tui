"""Coordinator module for Talos TUI."""
from __future__ import annotations

import asyncio
import logging
from enum import Enum, auto
from typing import Any, Dict, Set, Coroutine

from .state import (
    AuditEventsReceived,
    ErrorOccurred,
    RbacRolesUpdated,
    RbacBindingsUpdated,
    SecretsUpdated,
    KekStatusUpdated,
    ConfigUpdated,
    GovernanceLogsUpdated,
    BudgetsUpdated,
    VirtualKeysUpdated,
    TeamsUpdated,
    McpServersUpdated,
    McpPoliciesUpdated
)
from ..ports.errors import TuiError


logger = logging.getLogger(__name__)


class TuiState(Enum):
    """Enumeration of TUI states."""

    BOOT = auto()

    HANDSHAKE_GATEWAY = auto()
    HANDSHAKE_AUDIT = auto()
    RUNNING = auto()
    DEGRADED = auto()
    FATAL = auto()
    STOPPING = auto()


class Coordinator:
    """
    Coordinator: The central state machine and task manager.
    Invariants:
    - One handshake per dependency at a time.
    - Global retry budgets.
    - Lifecycle management of all background pollers.
    """

    def __init__(
        self,
        store: StateStore,
        gateway_adapter: Any,
        audit_adapter: Any,
        contracts_version_gate: str = "0",
        max_handshake_attempts: int = 5
    ):
        self.store = store
        self.gateway = gateway_adapter
        self.audit = audit_adapter
        self.state = TuiState.BOOT
        self.contracts_version_gate = contracts_version_gate
        self.max_handshake_attempts = max_handshake_attempts

        self._tasks: Set[asyncio.Task[Any]] = set()
        self._handshake_attempts: Dict[str, int] = {"gateway": 0, "audit": 0}
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the TUI lifecycle."""
        logger.info("Coordinator starting...")
        self.transition(TuiState.HANDSHAKE_GATEWAY)
        self.spawn(self._handshake_loop())

    def transition(self, new_state: TuiState) -> None:
        """Transition to a new state."""
        logger.info("Transition: %s -> %s", self.state.name, new_state.name)
        self.state = new_state
        if new_state == TuiState.FATAL:
            self.store.is_fatal = True

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Spawn a background task."""

        task: asyncio.Task[Any] = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def stop(self) -> None:
        """Stop the coordinator and cancel tasks."""
        self.transition(TuiState.STOPPING)

        self._stop_event.set()
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=2.0)
        logger.info("Coordinator stopped.")

    def retry(self) -> None:
        """Retry the handshake process manually."""
        logger.info("Manual retry triggered.")
        self._handshake_attempts = {"gateway": 0, "audit": 0}
        self.store.is_fatal = False
        self.store.global_error = None
        # Reset source errors explicitly to clear UI
        self.store.gateway.error = None
        self.store.audit.error = None

        self.transition(TuiState.HANDSHAKE_GATEWAY)
        self.spawn(self._handshake_loop())

    async def _handshake_loop(self) -> None:
        """Sequential handshake with backoff"""
        while not self._stop_event.is_set():
            if self.state == TuiState.HANDSHAKE_GATEWAY:
                await self._do_handshake("gateway")
            elif self.state == TuiState.HANDSHAKE_AUDIT:
                await self._do_handshake("audit")
            elif self.state == (
                TuiState.RUNNING
            ) or self.state == TuiState.DEGRADED:
                # Handshake complete, shift to polling
                self.spawn(self._poll_metrics())
                self.spawn(self._poll_audit())
                self.spawn(self._poll_rbac())
                self.spawn(self._poll_secrets())
                self.spawn(self._poll_config())
                self.spawn(self._poll_governance())
                self.spawn(self._poll_budgets())
                self.spawn(self._poll_keys())
                self.spawn(self._poll_mcp())
                return
            elif self.state == TuiState.FATAL:
                return

            await asyncio.sleep(1.0)

    async def _do_handshake(self, source: str) -> None:
        if self._handshake_attempts[source] >= self.max_handshake_attempts:
            self.transition(TuiState.FATAL)
            err = ErrorOccurred(
                source=source,
                kind="HANDSHAKE",
                message=f"Max attempts ({self.max_handshake_attempts}) "
                        f"exceeded",
                is_fatal=True
            )
            self.store.reduce(err)
            return

        self._handshake_attempts[source] += 1
        adapter = getattr(self, source)

        try:
            # 1. Health
            health = await adapter.get_health()
            self.store.reduce(
                HealthUpdated(
                    source=source,
                    is_ok=health.ok,
                    status_msg="READY" if health.ok else "NOT_READY"
                )
            )

            if not health.ok:
                raise TuiError(
                    kind="NOT_READY",
                    message=f"{source.capitalize()} not ready"
                )

            # 2. Version & Contract Gate
            ver = await adapter.get_version()
            self.store.reduce(
                VersionUpdated(
                    source=source,
                    version=ver.service_version,
                    contracts_version=ver.contracts_version
                )
            )

            major = ver.contracts_version.split(".")[0]
            if major != self.contracts_version_gate:
                self.transition(TuiState.FATAL)
                ver_err = ErrorOccurred(
                    source=source,
                    kind="CONTRACT",
                    message=f"Incompatible contracts: "
                            f"{ver.contracts_version}",
                    is_fatal=True
                )
                self.store.reduce(ver_err)
                return

            # Success -> Progress state machine
            if source == "gateway":
                self.transition(TuiState.HANDSHAKE_AUDIT)
            else:
                self.transition(TuiState.RUNNING)

        except TuiError as e:
            logger.warning("Handshake error for %s: %s", source, e.message)
            if e.kind in ("AUTH", "CONTRACT"):
                self.transition(TuiState.FATAL)

                fatal_err = ErrorOccurred(
                    source=source,
                    kind=e.kind,
                    message=e.message,
                    is_fatal=True
                )
                self.store.reduce(fatal_err)
            else:
                retry_err = ErrorOccurred(
                    source=source, kind=e.kind, message=e.message
                )
                self.store.reduce(retry_err)
                # Backoff
                delay = min(10, 2 ** self._handshake_attempts[source])
                await asyncio.sleep(delay)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Unexpected error in %s handshake", source)

            unk_err = ErrorOccurred(

                source=source, kind="UNKNOWN", message=str(e)
            )
            self.store.reduce(unk_err)
            await asyncio.sleep(2.0)

    async def _poll_metrics(self) -> None:
        while not self._stop_event.is_set():
            try:
                metrics = await self.gateway.get_metrics_summary()
                self.store.reduce(MetricsUpdated(metrics=metrics.dict()))
                if (
                    self.state == TuiState.DEGRADED
                    and self.store.gateway.health_ok
                ):
                    # Check if audit is also ok to go back to RUNNING
                    if self.store.audit.health_ok:
                        self.transition(TuiState.RUNNING)
            except TuiError as e:
                poll_err = ErrorOccurred(
                    source="gateway", kind=e.kind, message=e.message
                )
                self.store.reduce(poll_err)
                self.transition(TuiState.DEGRADED)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Metrics polling error: %s", e)

            await asyncio.sleep(2.0)

    async def _poll_audit(self) -> None:
        while not self._stop_event.is_set():

            try:
                page = await self.audit.list_events(limit=50)
                self.store.reduce(
                    AuditEventsReceived(
                        items=[item.dict() for item in page.items],
                        next_cursor=page.next_cursor
                    )
                )
                if (
                    self.state == TuiState.DEGRADED
                    and self.store.audit.health_ok
                ):
                    # Check if gateway is also ok to go back to RUNNING
                    if self.store.gateway.health_ok:
                        self.transition(TuiState.RUNNING)
            except TuiError as e:
                audit_err = ErrorOccurred(
                    source="audit", kind=e.kind, message=e.message
                )
                self.store.reduce(audit_err)
                self.transition(TuiState.DEGRADED)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Audit polling error: %s", e)

            await asyncio.sleep(2.0)

    async def _poll_rbac(self) -> None:
        """Poll RBAC roles and bindings from the gateway."""
        while not self._stop_event.is_set():
            try:
                # Fetch Roles
                roles = await self.gateway.list_rbac_roles()
                self.store.reduce(RbacRolesUpdated(roles=[r.model_dump() for r in roles]))

                # Fetch Bindings
                bindings = await self.gateway.list_rbac_bindings()
                self.store.reduce(RbacBindingsUpdated(bindings=[b.model_dump() for b in bindings]))

            except Exception as e:
                logger.error("RBAC polling error: %s", e)

            # RBAC configuration changes less frequently than metrics
            await asyncio.sleep(5.0)

    async def _poll_secrets(self) -> None:
        """Poll secrets and KEK status from the gateway."""
        while not self._stop_event.is_set():
            try:
                # Fetch Secrets
                secrets = await self.gateway.list_secrets()
                self.store.reduce(SecretsUpdated(secrets=[s.model_dump() for s in secrets]))

                # Fetch KEK status
                kek = await self.gateway.get_kek_status()
                self.store.reduce(KekStatusUpdated(status=kek.model_dump()))

            except Exception as e:
                logger.error("Secrets polling error: %s", e)

            await asyncio.sleep(5.0)

    async def _poll_config(self) -> None:
        """Poll platform configuration from the gateway."""
        while not self._stop_event.is_set():
            try:
                config = await self.gateway.export_config()
                self.store.reduce(ConfigUpdated(config=config.model_dump()))
            except Exception as e:
                logger.error("Config polling error: %s", e)

            # Platform configuration is heavy, poll infrequently
            await asyncio.sleep(30.0)

    async def _poll_governance(self) -> None:
        """Poll high-integrity governance logs from the gateway."""
        while not self._stop_event.is_set():
            try:
                logs = await self.gateway.list_governance_logs()
                self.store.reduce(GovernanceLogsUpdated(items=[l.model_dump() for l in logs]))
            except Exception as e:
                logger.error("Governance polling error: %s", e)

            await asyncio.sleep(5.0)

    async def _poll_budgets(self) -> None:
        """Poll budget scopes from the gateway."""
        while not self._stop_event.is_set():
            try:
                scopes = await self.gateway.list_budget_scopes()
                self.store.reduce(BudgetsUpdated(scopes=[s.model_dump() for s in scopes]))
            except Exception as e:
                logger.error("Budgets polling error: %s", e)

            await asyncio.sleep(5.0)

    async def _poll_keys(self) -> None:
        """Poll virtual keys and teams from the gateway."""
        while not self._stop_event.is_set():
            try:
                # Poll Keys
                keys = await self.gateway.list_virtual_keys()
                self.store.reduce(VirtualKeysUpdated(keys=[k.model_dump() for k in keys]))

                # Poll Teams
                teams = await self.gateway.list_teams()
                self.store.reduce(TeamsUpdated(teams=[t.model_dump() for t in teams]))
            except Exception as e:
                logger.error("Keys/Teams polling error: %s", e)

            await asyncio.sleep(10.0)

    async def _poll_mcp(self) -> None:
        """Poll MCP servers and policies from the gateway."""
        while not self._stop_event.is_set():
            try:
                # Poll Servers
                servers = await self.gateway.list_mcp_servers()
                self.store.reduce(McpServersUpdated(servers=[s.model_dump() for s in servers]))

                # Poll Policies
                policies = await self.gateway.list_mcp_policies()
                self.store.reduce(McpPoliciesUpdated(policies=[p.model_dump() for p in policies]))
            except Exception as e:
                logger.error("MCP polling error: %s", e)

            await asyncio.sleep(10.0)
