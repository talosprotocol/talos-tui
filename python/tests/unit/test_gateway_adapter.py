import pytest
from unittest.mock import AsyncMock
from aiohttp import ClientSession, ClientResponse
from talos_tui.adapters.gateway_http import HttpGatewayAdapter
from talos_tui.ports.errors import TuiError

@pytest.mark.asyncio
async def test_gateway_get_version_success() -> None:
    mock_resp = AsyncMock(spec=ClientResponse)
    mock_resp.status = 200
    mock_resp.content_length = 500
    mock_resp.json.return_value = {
        "version": "1.0.0",
        "git_sha": "abc",
        "contracts_version": "1.0.0",
        "api_version": "v1"
    }
    
    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_resp
    
    adapter = HttpGatewayAdapter("http://test", mock_session)
    version = await adapter.get_version()
    
    assert version.service_version == "1.0.0"
    assert version.contracts_version == "1.0.0"

@pytest.mark.asyncio
async def test_gateway_payload_too_large() -> None:
    mock_resp = AsyncMock(spec=ClientResponse)
    mock_resp.status = 200
    mock_resp.content_length = 2_000_000 # > 1MB limit
    
    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_resp
    
    adapter = HttpGatewayAdapter("http://test", mock_session)
    
    with pytest.raises(TuiError) as exc:
        await adapter.get_version()
    
    assert exc.value.kind == "PAYLOAD_TOO_LARGE"

@pytest.mark.asyncio
async def test_gateway_bad_status() -> None:
    mock_resp = AsyncMock(spec=ClientResponse)
    mock_resp.status = 500
    mock_resp.headers = {}
    
    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_resp
    
    adapter = HttpGatewayAdapter("http://test", mock_session)
    
    with pytest.raises(TuiError) as exc:
        await adapter.get_health()
        
    assert exc.value.kind == "NETWORK"
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_gateway_create_secret_sends_json_body() -> None:
    mock_resp = AsyncMock(spec=ClientResponse)
    mock_resp.status = 201
    mock_resp.content_length = 20
    mock_resp.json.return_value = {"success": True}

    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_resp

    adapter = HttpGatewayAdapter("http://test", mock_session)

    await adapter.create_secret("openai-key", "sk-test")

    _, _, kwargs = mock_session.request.mock_calls[0]
    assert kwargs["json"] == {"name": "openai-key", "value": "sk-test"}


@pytest.mark.asyncio
async def test_gateway_delete_mcp_policy_accepts_empty_204() -> None:
    mock_resp = AsyncMock(spec=ClientResponse)
    mock_resp.status = 204
    mock_resp.content_length = 0

    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_resp

    adapter = HttpGatewayAdapter("http://test", mock_session)

    await adapter.delete_mcp_policy("policy-eng")

    mock_session.request.assert_called_once()


@pytest.mark.asyncio
async def test_gateway_governance_logs_tolerates_missing_endpoint() -> None:
    mock_session = AsyncMock(spec=ClientSession)
    adapter = HttpGatewayAdapter("http://test", mock_session)
    adapter._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=TuiError(
            kind="BAD_RESPONSE",
            message="Endpoint not found (404)",
            status_code=404,
        )
    )

    assert await adapter.list_governance_logs() == []


@pytest.mark.asyncio
async def test_gateway_upsert_mcp_policy_uses_live_api_payload_shape() -> None:
    mock_resp = AsyncMock(spec=ClientResponse)
    mock_resp.status = 201
    mock_resp.content_length = 100
    mock_resp.json.return_value = {
        "id": "policy-eng",
        "team_id": "eng",
        "allowed_servers": ["filesystem"],
        "allowed_tools": ["tools/list"],
        "deny_by_default": True,
    }

    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_resp

    adapter = HttpGatewayAdapter("http://test", mock_session)

    policy = await adapter.upsert_mcp_policy(
        {
            "id": "policy-eng",
            "team_id": "eng",
            "allowed_servers": ["filesystem"],
            "allowed_tools": ["tools/list"],
            "enforcement_mode": "strict",
        }
    )

    _, _, kwargs = mock_session.request.mock_calls[0]
    assert kwargs["json"] == {
        "id": "policy-eng",
        "team_id": "eng",
        "allowed_servers": ["filesystem"],
        "allowed_tools": ["tools/list"],
        "deny_by_default": True,
    }
    assert policy.enforcement_mode == "strict"
