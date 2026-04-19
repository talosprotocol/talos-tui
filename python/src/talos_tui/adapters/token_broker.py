"""Async scoped JWT token broker for Talos TUI HTTP adapters."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any, Dict, Mapping, Sequence, Tuple
from uuid import uuid4

import aiohttp

from ..ports.errors import TuiError


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TokenResponse:
    """Response payload from the admin token mint endpoint."""

    token: str
    permissions: Tuple[str, ...]
    session_id: str
    expires_at: datetime
    expires_in: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "TokenResponse":
        """Parse and normalize a token response payload."""

        token = payload.get("token")
        permissions = payload.get("permissions", [])
        session_id = payload.get("session_id")
        expires_in = int(payload.get("expires_in", 0))
        expires_at_raw = payload.get("expires_at")

        if not isinstance(token, str) or not token:
            raise TuiError(
                kind="BAD_RESPONSE",
                message="Token mint response missing token",
            )
        if not isinstance(permissions, list) or not all(
            isinstance(permission, str) for permission in permissions
        ):
            raise TuiError(
                kind="BAD_RESPONSE",
                message="Token mint response permissions must be strings",
            )
        if not isinstance(session_id, str) or not session_id:
            raise TuiError(
                kind="BAD_RESPONSE",
                message="Token mint response missing session_id",
            )

        if isinstance(expires_at_raw, str) and expires_at_raw:
            expires_at = datetime.fromisoformat(
                expires_at_raw.replace("Z", "+00:00")
            )
        else:
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        return cls(
            token=token,
            permissions=tuple(permissions),
            session_id=session_id,
            expires_at=expires_at,
            expires_in=expires_in,
        )


@dataclass(frozen=True, slots=True)
class _TokenCacheEntry:
    token: str
    permissions: Tuple[str, ...]
    session_id: str
    expires_at: datetime
    expires_in: int


class AsyncScopedJwtTokenBroker:
    """Mint and cache scoped session JWTs for TUI HTTP requests."""

    def __init__(
        self,
        base_url: str,
        session: aiohttp.ClientSession,
        principal: str,
        admin_secret: str,
        data_plane_token: str | None = None,
        ttl_seconds: int = 3600,
        session_id: str | None = None,
        refresh_margin_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.principal = principal
        self.admin_secret = admin_secret
        self.data_plane_token = data_plane_token
        self.ttl_seconds = ttl_seconds
        self.session_id = session_id or str(uuid4())
        self.refresh_margin_seconds = refresh_margin_seconds
        self._cache: Dict[Tuple[str, ...], _TokenCacheEntry] = {}
        self._lock = asyncio.Lock()

    async def authorization_header(self, permissions: Sequence[str]) -> str:
        """Return a bearer authorization header for the requested scope."""

        token = await self._token_for_permissions(permissions)
        return f"Bearer {token}"

    async def invalidate(self, permissions: Sequence[str]) -> None:
        """Drop a cached token so the next request mints a fresh one."""

        key = self._normalized_permissions(permissions)
        async with self._lock:
            self._cache.pop(key, None)

    async def _token_for_permissions(self, permissions: Sequence[str]) -> str:
        key = self._normalized_permissions(permissions)
        cached = self._cache.get(key)
        if cached is not None and not self._is_expiring(cached):
            return cached.token

        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None and not self._is_expiring(cached):
                return cached.token

            entry = await self._mint_token(key)
            self._cache[key] = entry
            return entry.token

    async def _mint_token(self, permissions: Tuple[str, ...]) -> _TokenCacheEntry:
        url = f"{self.base_url}/admin/v1/auth/token"
        payload: Dict[str, Any] = {
            "principal": self.principal,
            "permissions": list(permissions),
            "ttl_seconds": self.ttl_seconds,
            "session_id": self.session_id,
        }
        if self.data_plane_token:
            payload["data_plane_token"] = self.data_plane_token

        headers = {"X-Talos-Admin-Secret": self.admin_secret}

        try:
            async with self.session.request(
                "POST",
                url,
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status in (401, 403):
                    raise TuiError(
                        kind="AUTH",
                        message=f"Token mint denied ({resp.status})",
                        status_code=resp.status,
                    )
                if resp.status >= 400:
                    raise TuiError(
                        kind="BAD_RESPONSE",
                        message=f"Token mint failed ({resp.status})",
                        status_code=resp.status,
                    )

                response_data = await resp.json()
                response = TokenResponse.from_payload(response_data)
                logger.info(
                    "Minted scoped JWT for permissions=%s session_id=%s ttl=%ss",
                    permissions,
                    response.session_id,
                    response.expires_in,
                )
                return _TokenCacheEntry(
                    token=response.token,
                    permissions=response.permissions,
                    session_id=response.session_id,
                    expires_at=response.expires_at,
                    expires_in=response.expires_in,
                )
        except asyncio.TimeoutError as exc:
            raise TuiError(
                kind="TIMEOUT",
                message="Token mint request timed out",
                retryable=True,
            ) from exc
        except aiohttp.ClientError as exc:
            raise TuiError(
                kind="NETWORK",
                message=str(exc),
                retryable=True,
            ) from exc

    def _is_expiring(self, entry: _TokenCacheEntry) -> bool:
        margin = min(
            self.refresh_margin_seconds,
            max(5.0, float(entry.expires_in) * 0.1),
        )
        return datetime.now(UTC) >= (entry.expires_at - timedelta(seconds=margin))

    @staticmethod
    def _normalized_permissions(permissions: Sequence[str]) -> Tuple[str, ...]:
        normalized = tuple(
            sorted(
                {
                    permission.strip()
                    for permission in permissions
                    if permission.strip()
                }
            )
        )
        if not normalized:
            raise ValueError("permissions must not be empty")
        return normalized
