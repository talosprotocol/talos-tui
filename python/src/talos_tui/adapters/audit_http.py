from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List
import aiohttp
from talos_tui.domain.models import AuditPage, AuditEvent, VersionInfo, Health
from talos_tui.adapters.base import BaseHttpAdapter
from talos_tui.ports.errors import TuiError

logger = logging.getLogger(__name__)

class HttpAuditAdapter(BaseHttpAdapter):
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
        data = await self._request("GET", "version")
        return VersionInfo(**data)

    async def get_health(self) -> Health:
        data = await self._request("GET", "health")
        return Health(**data)

    async def list_events(self, limit: int = 50, before: Optional[str] = None) -> AuditPage:
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
                    self.validator.validate("audit/audit_event.schema.json", i)
                
                items.append(AuditEvent(**i))
            except Exception as e:
                logger.error(f"Failed to parse or validate AuditEvent: {e}")

        return AuditPage(
            items=items,
            next_cursor=data.get("next_cursor"),
            has_more=data.get("has_more", False)
        )
