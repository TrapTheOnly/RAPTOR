import asyncio

import httpx
import pytest

import raptor_mcp.server as server_module
from raptor_mcp.settings import MCPSettings


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        raise NotImplementedError


def _settings() -> MCPSettings:
    return MCPSettings(
        mcp_server_token="token",
        raptor_service_api_key="service-key",
        raptor_api_base_url="http://app:5000",
        mcp_port=8081,
        raptor_api_timeout_seconds=30.0,
    )


def test_fetch_service_dataset_success(monkeypatch):
    class Client(_FakeAsyncClient):
        async def get(self, url, headers=None):
            assert url == "http://app:5000/service-api/v1/records"
            assert headers == {"X-API-Key": "service-key"}
            return _FakeResponse(200, {"count": 1, "records": [{"id": 1}]})

    monkeypatch.setattr(httpx, "AsyncClient", Client)

    payload = asyncio.run(server_module.fetch_service_dataset("/service-api/v1/records", _settings()))
    assert payload == {"count": 1, "records": [{"id": 1}]}


def test_fetch_service_dataset_pentests_success(monkeypatch):
    class Client(_FakeAsyncClient):
        async def get(self, url, headers=None):
            assert url == "http://app:5000/service-api/v1/pentests"
            assert headers == {"X-API-Key": "service-key"}
            return _FakeResponse(200, {"count": 1, "pentests": [{"id": 7}]})

    monkeypatch.setattr(httpx, "AsyncClient", Client)

    payload = asyncio.run(server_module.fetch_service_dataset("/service-api/v1/pentests", _settings()))
    assert payload == {"count": 1, "pentests": [{"id": 7}]}


@pytest.mark.parametrize("status_code", [401, 403, 500])
def test_fetch_service_dataset_maps_upstream_error(monkeypatch, status_code):
    class Client(_FakeAsyncClient):
        async def get(self, url, headers=None):
            return _FakeResponse(status_code, {"error": "Unauthorized access"})

    monkeypatch.setattr(httpx, "AsyncClient", Client)

    with pytest.raises(RuntimeError, match=rf"RAPTOR API error \({status_code}\): Unauthorized access"):
        asyncio.run(server_module.fetch_service_dataset("/service-api/v1/records", _settings()))


def test_fetch_service_dataset_maps_timeout(monkeypatch):
    class Client(_FakeAsyncClient):
        async def get(self, url, headers=None):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "AsyncClient", Client)

    with pytest.raises(RuntimeError, match="request timed out"):
        asyncio.run(server_module.fetch_service_dataset("/service-api/v1/records", _settings()))


def test_fetch_service_dataset_maps_connect_error(monkeypatch):
    class Client(_FakeAsyncClient):
        async def get(self, url, headers=None):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "AsyncClient", Client)

    with pytest.raises(RuntimeError, match="Failed to connect"):
        asyncio.run(server_module.fetch_service_dataset("/service-api/v1/records", _settings()))


def test_run_records_tool_sync_uses_records_path(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_fetch(path, settings):
        captured["path"] = path
        captured["settings"] = settings
        return {"records": []}

    monkeypatch.setattr(server_module, "fetch_service_dataset", fake_fetch)

    settings = _settings()
    payload = server_module.run_records_tool_sync(settings)
    assert payload == {"records": []}
    assert captured["path"] == "/service-api/v1/records"
    assert captured["settings"] is settings


def test_run_pentests_tool_sync_uses_pentests_path(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_fetch(path, settings):
        captured["path"] = path
        captured["settings"] = settings
        return {"pentests": []}

    monkeypatch.setattr(server_module, "fetch_service_dataset", fake_fetch)

    settings = _settings()
    payload = server_module.run_pentests_tool_sync(settings)
    assert payload == {"pentests": []}
    assert captured["path"] == "/service-api/v1/pentests"
    assert captured["settings"] is settings
