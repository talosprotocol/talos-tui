"""HTTP Adapter for Audit Service."""
from __future__ import annotations

import logging
from typing import Optional, Any
import aiohttp
from pydantic import ValidationError
from ..domain.models import AuditPage, AuditEvent, VersionInfo, Health
from .base import BaseHttpAdapter


logger = logging.getLogger(__name__)


class HttpAuditAdapter(BaseHttpAdapter):
    """Adapter for interacting with the Audit Service via HTTP."""

    def __init__(
        self,
        base_url: str,
        session: aiohttp.ClientSession,
        validator: Optional[Any] = None,
        version: str = "0.1.0",
        **kwargs: Any
    ):
        """
        @param base_url: The Base URL.
        @param session: The Client Session.
        @param validator: Functional Validator.
        @param version: API Version.
        """
        super().__init__(base_url, session, **kwargs)

        self.validator = validator
        self.headers = {"User-Agent": f"talos-tui/{version}"}

    async def get_version(self) -> VersionInfo:
        """Get service version information."""
        data = await self._request("GET", "version")
        return VersionInfo(**data)

    async def get_health(self) -> Health:
        """Get service health status."""
        data = await self._request("GET", "health")
        return Health(**data)

    async def list_events(
        self, limit: int = 50, before: Optional[str] = None
    ) -> AuditPage:
        """List audit events with pagination."""

        params = {"limit": str(limit)}
        if before:
            params["before"] = before

        data = await self._request("GET", "api/events", params=params)

        items_data = data.get("items", [])
        if not isinstance(items_data, list):
            items_data = []

        items = []
        for i in items_data:
            try:
                # Mechanized validation
                if self.validator:
                    self.validator.validate(
                        "audit/audit_event.schema.json", i
                    )

                items.append(AuditEvent(**i))
            except (ValidationError, TypeError, ValueError) as e:
                logger.error("Failed to parse or validate AuditEvent: %s", e)

        return AuditPage(
            items=items,
            next_cursor=data.get("next_cursor"),
            has_more=data.get("has_more", False)
        )
