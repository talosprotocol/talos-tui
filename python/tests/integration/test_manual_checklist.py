import pytest
import aiohttp
import asyncio
from aioresponses import aioresponses
from talos_tui.adapters.gateway_http import HttpGatewayAdapter
from talos_tui.ports.errors import TuiError

@pytest.mark.asyncio
async def test_403_fatal_failure():
    """Verify 403 on Gateway fails fast (Fatal)."""
    async with aiohttp.ClientSession() as session:
        adapter = HttpGatewayAdapter("http://localhost:8000", session)
        
        with aioresponses() as m:
            # HttpGatewayAdapter.get_health calls health/ready
            m.get("http://localhost:8000/health/ready", status=403)
            
            with pytest.raises(TuiError) as exc:
                await adapter.get_health()
            
            assert exc.value.kind == "AUTH"
            assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_500_transient_backoff_and_retry():
    """Verify 5xx triggers backoff and retry until success."""
    async with aiohttp.ClientSession() as session:
        # Set max_attempts higher and mock sleep to speed up test
        adapter = HttpGatewayAdapter("http://localhost:8000", session, max_attempts=3)
        
        with aioresponses() as m:
            # 1st attempt: 500
            m.get("http://localhost:8000/health/ready", status=500)
            # 2nd attempt: Success (Health model expects status="ok")
            m.get("http://localhost:8000/health/ready", status=200, body='{"status": "ok"}')
            
            # Patch sleep to avoid waiting
            from unittest.mock import patch
            with patch("asyncio.sleep", return_value=None):
                health = await adapter.get_health()
                assert health.ok is True

@pytest.mark.asyncio
async def test_payload_size_capping():
    """Verify response exceeds limit (1MB) triggers PAYLOAD_TOO_LARGE."""
    async with aiohttp.ClientSession() as session:
        # Set a small limit for testing
        adapter = HttpGatewayAdapter("http://localhost:8000", session, max_response_size=100)
        
        with aioresponses() as m:
            # We must provide Content-Length header to trigger the pre-json() check
            m.get(
                "http://localhost:8000/health/ready", 
                status=200, 
                body="x" * 200,
                headers={"Content-Length": "200"}
            )
            
            with pytest.raises(TuiError) as exc:
                await adapter.get_health()
            
            assert exc.value.kind == "PAYLOAD_TOO_LARGE"
