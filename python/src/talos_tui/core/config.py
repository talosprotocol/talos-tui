"""Configuration helpers for the Talos TUI."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Tuple


def _split_csv(value: str | None) -> Tuple[str, ...]:
    """Split a comma-separated environment value into normalized items."""

    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _get_first_env(*names: str, default: str) -> str:
    """Return the first configured environment value or the default."""

    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


@dataclass(frozen=True, slots=True)
class TuiAuthConfig:
    """Authentication inputs for the TUI's scoped JWT broker."""

    principal: str
    admin_secret: str
    data_plane_token: str | None
    gateway_permissions: Tuple[str, ...]
    audit_permissions: Tuple[str, ...]
    ttl_seconds: int = 3600
    session_id: str | None = None

    @classmethod
    def from_env(cls) -> "TuiAuthConfig":
        """Build auth config from environment variables."""

        principal = _get_first_env(
            "TALOS_TUI_AUTH_PRINCIPAL",
            "TALOS_TUI_ADMIN_PRINCIPAL",
            "AUTH_ADMIN_PRINCIPAL",
            default="dev-admin",
        )
        admin_secret = _get_first_env(
            "TALOS_TUI_ADMIN_SECRET",
            "AUTH_ADMIN_SECRET",
            "AUTH_SECRET",
            default="",
        )
        data_plane_token = _get_first_env(
            "TALOS_TUI_DATA_PLANE_TOKEN",
            "TALOS_API_TOKEN",
            "AUTH_TOKEN",
            default="",
        )
        gateway_permissions = _split_csv(
            os.getenv("TALOS_TUI_GATEWAY_PERMISSIONS")
        ) or ("llm.read", "mcp.read", "audit.read")
        audit_permissions = _split_csv(
            os.getenv("TALOS_TUI_AUDIT_PERMISSIONS")
        ) or ("audit.read",)
        ttl_seconds = int(os.getenv("TALOS_TUI_TOKEN_TTL_SECONDS", "3600"))
        session_id = _get_first_env(
            "TALOS_TUI_AUTH_SESSION_ID",
            "TALOS_TUI_SESSION_ID",
            default="",
        )

        return cls(
            principal=principal,
            admin_secret=admin_secret,
            data_plane_token=data_plane_token or None,
            gateway_permissions=gateway_permissions,
            audit_permissions=audit_permissions,
            ttl_seconds=ttl_seconds,
            session_id=session_id or None,
        )
