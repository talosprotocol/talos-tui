"""HTTP Adapter for Gateway Service."""
from __future__ import annotations

import logging
from typing import Sequence, Optional, Any
import aiohttp
from ..domain.models import (
    Health, MetricsSummary, Peer, Session, VersionInfo
)
from .base import BaseHttpAdapter


logger = logging.getLogger(__name__)


class HttpGatewayAdapter(BaseHttpAdapter):
    """Adapter for interacting with the Gateway Service via HTTP."""

    def __init__(
        self,
        base_url: str,
        session: aiohttp.ClientSession,
        validator: Optional[Any] = None,
        version: str = "0.1.0",
        **kwargs: Any
    ):
        super().__init__(base_url, session, **kwargs)
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
