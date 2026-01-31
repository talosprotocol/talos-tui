from __future__ import annotations
import asyncio
import logging
from enum import Enum, auto
from typing import Any, Dict, Optional, List, Set, Coroutine, cast

from talos_tui.core.state import (
    StateStore, 
    HealthUpdated, 
    VersionUpdated, 
    MetricsUpdated, 
    AuditEventsReceived, 
    ErrorOccurred
)
from talos_tui.ports.errors import TuiError

logger = logging.getLogger(__name__)

class TuiState(Enum):
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
        """Start the TUI lifecycle"""
        logger.info("Coordinator starting...")
        self.transition(TuiState.HANDSHAKE_GATEWAY)
        self.spawn(self._handshake_loop())

    def transition(self, new_state: TuiState) -> None:
        logger.info(f"Transition: {self.state.name} -> {new_state.name}")
        self.state = new_state
        if new_state == TuiState.FATAL:
             self.store.is_fatal = True

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task: asyncio.Task[Any] = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def stop(self) -> None:
        self.transition(TuiState.STOPPING)
        self._stop_event.set()
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=2.0)
        logger.info("Coordinator stopped.")

    async def _handshake_loop(self) -> None:
        """Sequential handshake with backoff"""
        while not self._stop_event.is_set():
            if self.state == TuiState.HANDSHAKE_GATEWAY:
                await self._do_handshake("gateway")
            elif self.state == TuiState.HANDSHAKE_AUDIT:
                await self._do_handshake("audit")
            elif self.state == TuiState.RUNNING or self.state == TuiState.DEGRADED:
                # Handshake complete, shift to polling
                self.spawn(self._poll_metrics())
                self.spawn(self._poll_audit())
                return
            elif self.state == TuiState.FATAL:
                return
            
            await asyncio.sleep(1.0)

    async def _do_handshake(self, source: str) -> None:
        if self._handshake_attempts[source] >= self.max_handshake_attempts:
            self.transition(TuiState.FATAL)
            self.store.reduce(ErrorOccurred(source=source, kind="HANDSHAKE", message=f"Max attempts ({self.max_handshake_attempts}) exceeded", is_fatal=True))
            return

        self._handshake_attempts[source] += 1
        adapter = getattr(self, source)
        
        try:
            # 1. Health
            health = await adapter.get_health()
            self.store.reduce(HealthUpdated(source=source, is_ok=health.ok, status_msg="READY" if health.ok else "NOT_READY"))
            
            if not health.ok:
                raise TuiError(kind="NOT_READY", message=f"{source.capitalize()} not ready")

            # 2. Version & Contract Gate
            ver = await adapter.get_version()
            self.store.reduce(VersionUpdated(source=source, version=ver.service_version, contracts_version=ver.contracts_version))
            
            major = ver.contracts_version.split(".")[0]
            if major != self.contracts_version_gate:
                self.transition(TuiState.FATAL)
                self.store.reduce(ErrorOccurred(source=source, kind="CONTRACT", message=f"Incompatible contracts: {ver.contracts_version}", is_fatal=True))
                return

            # Success -> Progress state machine
            if source == "gateway":
                self.transition(TuiState.HANDSHAKE_AUDIT)
            else:
                self.transition(TuiState.RUNNING)

        except TuiError as e:
            logger.warning(f"Handshake error for {source}: {e.message}")
            if e.kind in ("AUTH", "CONTRACT"):
                self.transition(TuiState.FATAL)
                self.store.reduce(ErrorOccurred(source=source, kind=e.kind, message=e.message, is_fatal=True))
            else:
                self.store.reduce(ErrorOccurred(source=source, kind=e.kind, message=e.message))
                # Backoff before next attempt is handled by loop or manual sleep
                await asyncio.sleep(min(10, 2 ** self._handshake_attempts[source]))
        except Exception as e:
            logger.exception(f"Unexpected error in {source} handshake")
            self.store.reduce(ErrorOccurred(source=source, kind="UNKNOWN", message=str(e)))
            await asyncio.sleep(2.0)

    async def _poll_metrics(self) -> None:
        while not self._stop_event.is_set():
            try:
                metrics = await self.gateway.get_metrics_summary()
                self.store.reduce(MetricsUpdated(metrics=metrics.dict()))
                if self.state == TuiState.DEGRADED and self.store.gateway.health_ok:
                    # Check if audit is also ok to go back to RUNNING
                    if self.store.audit.health_ok:
                        self.transition(TuiState.RUNNING)
            except TuiError as e:
                self.store.reduce(ErrorOccurred(source="gateway", kind=e.kind, message=e.message))
                self.transition(TuiState.DEGRADED)
            except Exception as e:
                logger.error(f"Metrics polling error: {e}")
            await asyncio.sleep(2.0)

    async def _poll_audit(self) -> None:
        while not self._stop_event.is_set():
            try:
                page = await self.audit.list_events(limit=50)
                self.store.reduce(AuditEventsReceived(items=[item.dict() for item in page.items], next_cursor=page.next_cursor))
            except TuiError as e:
                self.store.reduce(ErrorOccurred(source="audit", kind=e.kind, message=e.message))
                self.transition(TuiState.DEGRADED)
            except Exception as e:
                logger.error(f"Audit polling error: {e}")
            await asyncio.sleep(2.0)
