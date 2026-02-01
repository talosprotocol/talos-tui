"""Domain models for Talos TUI."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ViewModel(BaseModel):
    """Base view model with common configuration."""

    model_config = ConfigDict(extra="ignore")


class VersionInfo(ViewModel):
    """Version information model."""

    service_version: str = Field(alias="version")

    git_sha: str
    contracts_version: str = "1.0.0"
    api_version: str = "1.0.0"


class Health(ViewModel):
    """Health status model."""

    status: str = "error"

    detail: Optional[str] = None

    def ok(self) -> bool:
        """Check if status is ok."""
        return self.status == "ok"


class MetricsSummary(ViewModel):
    """Metrics summary model."""

    latency_p50_ms: float = 0.0

    latency_p95_ms: float = 0.0
    connected_peers: int = 0
    active_sessions: int = 0


class Peer(ViewModel):
    """Peer information model."""

    peer_id: str

    services: List[str] = Field(default_factory=list)


class Session(ViewModel):
    """Session information model."""

    session_id: str

    peer_id: Optional[str] = None
    created_at: Optional[str] = None


class AuditEvent(ViewModel):
    """Audit event model."""

    id: str = Field(alias="event_id")

    ts: str
    event_type: str = Field(alias="schema_id")
    outcome: str = "OK"
    payload: Dict[str, Any] = Field(default_factory=dict)


class AuditPage(ViewModel):
    """Audit page model."""

    items: List[AuditEvent] = Field(default_factory=list)

    next_cursor: Optional[str] = None
    has_more: bool = False
