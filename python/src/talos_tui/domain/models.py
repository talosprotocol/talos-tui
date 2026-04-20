"""Domain models for Talos TUI."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, AliasChoices


class ViewModel(BaseModel):
    """Base view model with common configuration."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


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

    @property
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
    """Audit event model aligned with ai-gateway v1 schema."""

    event_id: str
    ts: str = Field(validation_alias=AliasChoices("ts", "timestamp"))
    request_id: Optional[str] = None
    surface_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("surface_id", "action"))
    outcome: Optional[str] = Field(default=None, validation_alias=AliasChoices("outcome", "status"))
    
    principal: Dict[str, Any] = Field(default_factory=dict)
    http: Dict[str, Any] = Field(default_factory=dict)
    
    schema_id: str = "talos.audit_event"
    schema_version: str = "v1"
    
    meta: Dict[str, Any] = Field(default_factory=dict, validation_alias=AliasChoices("meta", "details", "payload"))
    resource: Optional[Dict[str, Any]] = None
    event_hash: Optional[str] = None

    @property
    def id(self) -> str:
        """Alias for event_id."""
        return self.event_id

    @property
    def payload(self) -> Dict[str, Any]:
        """Alias for meta."""
        return self.meta


class BudgetScope(ViewModel):
    """Budget Scope model for Phase 15."""

    id: str
    scope_type: str  # team, virtual_key
    scope_id: str
    period_start: str
    limit_usd: float = 0.0
    used_usd: float = 0.0
    reserved_usd: float = 0.0
    overdraft_usd: float = 0.0


class BudgetReservation(ViewModel):
    """Budget Reservation model for Phase 15."""

    id: str
    request_id: str
    scope_team_id: str
    scope_key_id: str
    reserved_usd: float
    status: str
    expires_at: str
    created_at: str


class AuditPage(ViewModel):
    """Audit page model."""

    items: List[AuditEvent] = Field(default_factory=list)

    next_cursor: Optional[str] = None
    has_more: bool = False

class RbacScope(ViewModel):
    scope_type: str
    attributes: Dict[str, str] = Field(default_factory=dict)

class RbacRole(ViewModel):
    role_id: str
    name: str
    permissions: List[str]
    built_in: bool = False
    description: Optional[str] = None

class RbacBindingEntry(ViewModel):
    binding_id: str
    role_id: str
    scope: RbacScope

class RbacBinding(ViewModel):
    principal_id: str
    team_id: Optional[str] = None
    bindings: List[RbacBindingEntry] = Field(default_factory=list)

class Secret(ViewModel):
    """Model for a secret metadata."""
    name: str
    kek_id: Optional[str] = None  # KEK used to encrypt this secret
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class KekStatus(ViewModel):
    """Model for Key Encryption Key status."""
    current_kek_id: str
    loaded_kek_ids: List[str]
    stale_counts: Dict[str, int]

class RotationOperation(ViewModel):
    """Model for a background rotation operation.
    
    The rotate-all endpoint returns `op_id`; the status endpoint returns `id`.
    AliasChoices handles both.
    """
    id: str = Field(validation_alias=AliasChoices("id", "op_id"))
    status: str
    target_kek_id: str = ""
    stats: Dict[str, int] = Field(default_factory=lambda: {"scanned": 0, "rotated": 0, "failed": 0})
    started_at: str = ""
    completed_at: Optional[str] = None
    last_error: Optional[str] = None

class GovernanceEntry(ViewModel):
    """Governance entry model."""
    trace_id: str
    sequence_number: int
    artifact_type: str
    ts: str
    status: str
    principal_id: str
    artifact_id: str

class ConfigExport(ViewModel):
    """Model for platform configuration export."""
    upstreams: Dict[str, Any]
    model_groups: Dict[str, Any]
    routing_policies: Dict[str, Any]
