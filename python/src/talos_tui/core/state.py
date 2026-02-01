"""TUI State Management."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True, kw_only=True)
class TuiEvent:
    """Base class for all TUI state change events"""

    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True, kw_only=True)
class HealthUpdated(TuiEvent):
    """Event for health status updates."""

    source: str  # "gateway" or "audit"
    is_ok: bool
    status_msg: str = ""


@dataclass(frozen=True, kw_only=True)
class VersionUpdated(TuiEvent):
    """Event for version updates."""

    source: str
    version: str
    contracts_version: str


@dataclass(frozen=True, kw_only=True)
class MetricsUpdated(TuiEvent):
    """Event for metrics updates."""

    metrics: Dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class AuditEventsReceived(TuiEvent):
    """Event for received audit logs."""

    items: List[Dict[str, Any]]
    next_cursor: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class ErrorOccurred(TuiEvent):
    """Event for errors."""

    source: str
    kind: str
    message: str
    is_fatal: bool = False


@dataclass(kw_only=True)
class SourceState:
    """State of a single data source."""

    health_ok: bool = False
    status_msg: str = "INITIALIZING"
    version: Optional[str] = None
    contracts_version: Optional[str] = None
    last_updated_at: float = 0
    error: Optional[str] = None


@dataclass(kw_only=True)
class StateStore:
    """
    StateStore: Pure data + Pure updates.
    UI elements should render based on projections of this state.
    """
    gateway: SourceState = field(default_factory=SourceState)
    audit: SourceState = field(default_factory=SourceState)
    metrics: Dict[str, Any] = field(default_factory=dict)
    audit_events: List[Dict[str, Any]] = field(default_factory=list)
    audit_cursor: Optional[str] = None

    _seen_audit_ids: Set[str] = field(default_factory=set)
    global_error: Optional[str] = None
    is_fatal: bool = False

    def reduce(self, event: TuiEvent) -> None:
        """Apply a pure event to the state"""
        if isinstance(event, HealthUpdated):
            source = getattr(self, event.source)
            source.health_ok = event.is_ok
            source.status_msg = event.status_msg
            source.last_updated_at = event.timestamp
            if event.is_ok:
                source.error = None

        elif isinstance(event, VersionUpdated):
            source = getattr(self, event.source)
            source.version = event.version
            source.contracts_version = event.contracts_version
            source.last_updated_at = event.timestamp

        elif isinstance(event, MetricsUpdated):
            self.metrics = event.metrics
            self.gateway.last_updated_at = event.timestamp

        elif isinstance(event, AuditEventsReceived):
            # deduplicate and append
            new_items = []
            for item in event.items:
                eid = item.get("event_id") or item.get("id")
                if eid and eid not in self._seen_audit_ids:
                    new_items.append(item)
                    self._seen_audit_ids.add(eid)
                    new_items.append(item)
                    self._seen_audit_ids.add(eid)

            # Keep only last 1000 items in memory
            self.audit_events = (new_items + self.audit_events)[:1000]
            self.audit_cursor = event.next_cursor
            self.audit.last_updated_at = event.timestamp

        elif isinstance(event, ErrorOccurred):
            source = getattr(self, event.source)
            source.error = event.message
            source.last_updated_at = event.timestamp
            if event.is_fatal:
                self.global_error = f"FATAL [{event.source}]: {event.message}"
                self.is_fatal = True

    def get_stale_since(self, source: str) -> float:
        """Returns how many seconds since the last update for a source"""
        s = getattr(self, source)
        if s.last_updated_at == 0:
            return float('inf')
        return float(time.time() - s.last_updated_at)
