import pytest
from aiohttp import ClientResponse, ClientSession
from unittest.mock import AsyncMock, MagicMock

from talos_tui.adapters.base import BaseHttpAdapter
from talos_tui.adapters.token_broker import AsyncScopedJwtTokenBroker


class _ResponseContext:
    def __init__(self, response: ClientResponse) -> None:
        self._response = response

    async def __aenter__(self) -> ClientResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _token_response(
    token: str,
    expires_in: int = 3600,
    expires_at: str = "2099-01-01T00:00:00Z",
) -> ClientResponse:
    resp = AsyncMock(spec=ClientResponse)
    resp.status = 200
    resp.json = AsyncMock(
        return_value={
            "token": token,
            "permissions": ["audit.read"],
            "session_id": "sess-1",
            "expires_in": expires_in,
            "expires_at": expires_at,
        }
    )
    return resp


@pytest.mark.asyncio
async def test_token_broker_caches_by_permission_set() -> None:
    session = AsyncMock(spec=ClientSession)
    session.request.return_value = _ResponseContext(_token_response("jwt-1"))

    broker = AsyncScopedJwtTokenBroker(
        "http://gateway",
        session,
        principal="dev-admin",
        admin_secret="dev-admin-secret",
    )

    header_1 = await broker.authorization_header(["audit.read", "llm.read"])
    header_2 = await broker.authorization_header(["llm.read", "audit.read"])

    assert header_1 == "Bearer jwt-1"
    assert header_2 == "Bearer jwt-1"
    assert session.request.call_count == 1


@pytest.mark.asyncio
async def test_token_broker_refreshes_near_expiry() -> None:
    session = AsyncMock(spec=ClientSession)
    first = _token_response(
        "jwt-1",
        expires_in=1,
        expires_at="2000-01-01T00:00:00Z",
    )
    second = _token_response("jwt-2", expires_in=3600)
    session.request.side_effect = [
        _ResponseContext(first),
        _ResponseContext(second),
    ]

    broker = AsyncScopedJwtTokenBroker(
        "http://gateway",
        session,
        principal="dev-admin",
        admin_secret="dev-admin-secret",
    )

    header_1 = await broker.authorization_header(["audit.read"])
    header_2 = await broker.authorization_header(["audit.read"])

    assert header_1 == "Bearer jwt-1"
    assert header_2 == "Bearer jwt-2"
    assert session.request.call_count == 2


@pytest.mark.asyncio
async def test_http_adapter_retries_after_auth_refresh() -> None:
    session = AsyncMock(spec=ClientSession)

    mint_first = AsyncMock(spec=ClientResponse)
    mint_first.status = 200
    mint_first.json = AsyncMock(
        return_value={
            "token": "jwt-1",
            "permissions": ["llm.read"],
            "session_id": "sess-1",
            "expires_in": 3600,
            "expires_at": "2099-01-01T00:00:00Z",
        }
    )

    mint_second = AsyncMock(spec=ClientResponse)
    mint_second.status = 200
    mint_second.json = AsyncMock(
        return_value={
            "token": "jwt-2",
            "permissions": ["llm.read"],
            "session_id": "sess-1",
            "expires_in": 3600,
            "expires_at": "2099-01-01T00:00:00Z",
        }
    )

    denied = AsyncMock(spec=ClientResponse)
    denied.status = 401
    denied.content_length = 10
    denied.headers = {}

    ok = AsyncMock(spec=ClientResponse)
    ok.status = 200
    ok.content_length = 100
    ok.headers = {}
    ok.json = AsyncMock(
        return_value={
            "version": "1.0.0",
            "git_sha": "abc",
            "contracts_version": "1.0.0",
            "api_version": "v1",
        }
    )

    calls = {"count": 0}

    def request_side_effect(method, url, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        current = calls["count"]
        if str(url).endswith("/admin/v1/auth/token"):
            if current == 1:
                return _ResponseContext(mint_first)
            return _ResponseContext(mint_second)
        if current == 2:
            assert kwargs["headers"]["Authorization"] == "Bearer jwt-1"
            return _ResponseContext(denied)
        assert kwargs["headers"]["Authorization"] == "Bearer jwt-2"
        return _ResponseContext(ok)

    session.request.side_effect = request_side_effect

    broker = AsyncScopedJwtTokenBroker(
        "http://gateway",
        session,
        principal="dev-admin",
        admin_secret="dev-admin-secret",
    )

    adapter = BaseHttpAdapter(
        "http://gateway",
        session,
        auth_broker=broker,
        auth_permissions=("llm.read",),
    )

    data = await adapter._request("GET", "version")

    assert data["version"] == "1.0.0"
    assert session.request.call_count == 4
