import asyncio
import json

import httpx
import pytest

import raptor_mcp.server as server_module
import raptor_mcp.write_tools as write_tools_module
from raptor_mcp.settings import MCPSettings
from raptor_mcp.write_tools import _calculate_cvss_base


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

    async def patch(self, url, json=None, headers=None):
        raise NotImplementedError

    async def post(self, url, json=None, headers=None):
        raise NotImplementedError

    async def put(self, url, json=None, headers=None):
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


def test_fetch_all_service_pages_walks_until_short_page(monkeypatch):
    from raptor_mcp.http_client import LIST_PAGE_SIZE, fetch_all_service_pages

    requests = []

    class Client(_FakeAsyncClient):
        async def get(self, url, headers=None, params=None):
            requests.append(dict(params or {}))
            offset = int((params or {}).get("offset") or 0)
            if offset == 0:
                page = [{"id": index} for index in range(LIST_PAGE_SIZE)]
            else:
                page = [{"id": LIST_PAGE_SIZE}]
            return _FakeResponse(
                200,
                {
                    "count": len(page),
                    "limit": LIST_PAGE_SIZE,
                    "offset": offset,
                    "records": page,
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    payload = asyncio.run(
        fetch_all_service_pages("/service-api/v1/records", "records", _settings())
    )
    assert payload["count"] == LIST_PAGE_SIZE + 1
    assert [row["id"] for row in payload["records"]] == list(range(LIST_PAGE_SIZE + 1))
    assert requests[0]["limit"] == LIST_PAGE_SIZE
    assert requests[1]["offset"] == LIST_PAGE_SIZE


def test_run_records_tool_sync_uses_records_path(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_fetch(path, collection_key, settings):
        captured["path"] = path
        captured["collection_key"] = collection_key
        captured["settings"] = settings
        return {"records": []}

    monkeypatch.setattr(server_module, "fetch_all_service_pages", fake_fetch)

    settings = _settings()
    payload = server_module.run_records_tool_sync(settings)
    assert payload == {"records": []}
    assert captured["path"] == "/service-api/v1/records"
    assert captured["collection_key"] == "records"
    assert captured["settings"] is settings


def test_run_pentests_tool_sync_uses_pentests_path(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_fetch(path, collection_key, settings):
        captured["path"] = path
        captured["collection_key"] = collection_key
        captured["settings"] = settings
        return {"pentests": []}

    monkeypatch.setattr(server_module, "fetch_all_service_pages", fake_fetch)

    settings = _settings()
    payload = server_module.run_pentests_tool_sync(settings)
    assert payload == {"pentests": []}
    assert captured["path"] == "/service-api/v1/pentests"
    assert captured["collection_key"] == "pentests"
    assert captured["settings"] is settings


# ── mutate_service_dataset ──────────────────────────────────────────────────

def test_mutate_service_dataset_success(monkeypatch):
    class Client(_FakeAsyncClient):
        async def patch(self, url, json=None, headers=None):
            assert url == "http://app:5000/service-api/v1/pentests/1"
            assert headers.get("X-RAPTOR-Scanner") == "1"
            assert headers.get("X-API-Key") == "service-key"
            return _FakeResponse(200, {"message": "Pentest updated."})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    result = asyncio.run(
        write_tools_module.mutate_service_dataset("patch", "/service-api/v1/pentests/1", {}, _settings())
    )
    assert result == {"message": "Pentest updated."}


@pytest.mark.parametrize("status_code", [400, 403, 500])
def test_mutate_service_dataset_propagates_error(monkeypatch, status_code):
    class Client(_FakeAsyncClient):
        async def patch(self, url, json=None, headers=None):
            return _FakeResponse(status_code, {"error": "bad"})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    with pytest.raises(RuntimeError, match=rf"RAPTOR API error \({status_code}\)"):
        asyncio.run(
            write_tools_module.mutate_service_dataset("patch", "/service-api/v1/pentests/1", {}, _settings())
        )


def test_mutate_service_dataset_timeout(monkeypatch):
    class Client(_FakeAsyncClient):
        async def patch(self, url, json=None, headers=None):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    with pytest.raises(RuntimeError, match="timed out"):
        asyncio.run(
            write_tools_module.mutate_service_dataset("patch", "/service-api/v1/pentests/1", {}, _settings())
        )


# ── get_checklist_templates ─────────────────────────────────────────────────

def test_get_checklist_templates_uses_correct_path(monkeypatch):
    class Client(_FakeAsyncClient):
        async def get(self, url, headers=None):
            assert url == "http://app:5000/service-api/v1/checklist-templates"
            return _FakeResponse(200, {"count": 1, "templates": [{"key": "ssh-security"}]})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    result = asyncio.run(server_module.fetch_service_dataset("/service-api/v1/checklist-templates", _settings()))
    assert result["count"] == 1


# ── update_pentest_ports ────────────────────────────────────────────────────

def test_update_pentest_ports_sends_correct_body(monkeypatch):
    captured: dict = {}

    class Client(_FakeAsyncClient):
        async def patch(self, url, json=None, headers=None):
            captured["url"] = url
            captured["body"] = json
            return _FakeResponse(200, {"message": "Pentest updated."})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    asyncio.run(write_tools_module.do_update_pentest_ports(7, "22,80,443", _settings()))
    assert captured["url"].endswith("/pentests/7")
    assert captured["body"] == {"open_ports": "22,80,443"}


# ── add_pentest_vulnerability ───────────────────────────────────────────────

def test_calculate_cvss_base_high_severity():
    metrics = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}
    score = _calculate_cvss_base(metrics)
    assert score >= 9.0


def test_calculate_cvss_base_zero_impact():
    metrics = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "N", "I": "N", "A": "N"}
    assert _calculate_cvss_base(metrics) == 0.0


def test_add_pentest_vulnerability_posts_to_dedicated_endpoint(monkeypatch):
    post_captured: dict = {}

    class Client(_FakeAsyncClient):
        async def post(self, url, json=None, headers=None):
            post_captured["url"] = url
            post_captured["body"] = json
            post_captured["headers"] = headers or {}
            return _FakeResponse(200, {"message": "Vulnerability appended."})

    monkeypatch.setattr(httpx, "AsyncClient", Client)

    asyncio.run(
        write_tools_module.do_add_pentest_vulnerability(
            3, "XSS in login", "", "N", "L", "N", "N", "U", "N", "L", "N", _settings()
        )
    )
    assert post_captured["url"].endswith("/pentests/3/vulnerabilities")
    assert post_captured["body"]["description"] == "XSS in login"
    assert post_captured["body"]["created_by"] == "RAPTOR-Scanner"
    assert post_captured["body"]["baseScore"] > 0
    assert post_captured["headers"].get("X-RAPTOR-Scanner") == "1"


# ── update_checklist_item ───────────────────────────────────────────────────

def test_update_checklist_item_adds_template_and_sets_status(monkeypatch):
    pentest_response = {
        "pentest": {"record_id": 5, "checklist_states": json.dumps({"selected": [], "statuses": {}})}
    }
    patch_captured: dict = {}

    async def fake_fetch(path, settings):
        return pentest_response

    class Client(_FakeAsyncClient):
        async def patch(self, url, json=None, headers=None):
            patch_captured["body"] = json
            return _FakeResponse(200, {"message": "ok"})

    monkeypatch.setattr(write_tools_module, "fetch_service_dataset", fake_fetch)
    monkeypatch.setattr(httpx, "AsyncClient", Client)

    asyncio.run(
        write_tools_module.do_update_checklist_item(5, "ssh-security", "SSH-001", "completed", _settings())
    )
    states = json.loads(patch_captured["body"]["checklist_states"])
    assert "ssh-security" in states["selected"]
    assert states["statuses"]["ssh-security"]["SSH-001"] == "completed"


def test_update_checklist_item_preserves_legacy_flat_statuses(monkeypatch):
    pentest_response = {
        "pentest": {
            "record_id": 5,
            "checklist_states": json.dumps(
                {"selected": ["owasp-web"], "statuses": {"INFO-001": "completed"}}
            ),
        }
    }
    patch_captured: dict = {}

    async def fake_fetch(path, settings):
        return pentest_response

    class Client(_FakeAsyncClient):
        async def patch(self, url, json=None, headers=None):
            patch_captured["body"] = json
            return _FakeResponse(200, {"message": "ok"})

    monkeypatch.setattr(write_tools_module, "fetch_service_dataset", fake_fetch)
    monkeypatch.setattr(httpx, "AsyncClient", Client)

    asyncio.run(
        write_tools_module.do_update_checklist_item(5, "ssh-security", "SSH-001", "completed", _settings())
    )
    states = json.loads(patch_captured["body"]["checklist_states"])
    assert states["statuses"]["INFO-001"] == "completed"
    assert states["statuses"]["ssh-security"]["SSH-001"] == "completed"


def test_update_checklist_item_rejects_invalid_status():
    with pytest.raises(ValueError, match="status must be one of"):
        asyncio.run(
            write_tools_module.do_update_checklist_item(5, "ssh-security", "SSH-001", "bad_status", _settings())
        )


# ── notify_scan_complete ────────────────────────────────────────────────────

def test_notify_scan_complete_sends_correct_body(monkeypatch):
    post_captured: dict = {}

    class Client(_FakeAsyncClient):
        async def post(self, url, json=None, headers=None):
            post_captured["url"] = url
            post_captured["body"] = json
            return _FakeResponse(200, {"message": "Notifications sent."})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    asyncio.run(
        write_tools_module.do_notify_scan_complete(4, 3, 12000, 4000, 80000, 12000, 0.14, _settings())
    )
    assert post_captured["url"].endswith("/pentests/4/notify-scan-complete")
    assert post_captured["body"]["findings_count"] == 3
    assert post_captured["body"]["cache_read_input_tokens"] == 80000
    assert post_captured["body"]["cache_creation_input_tokens"] == 12000
    assert post_captured["body"]["cost_usd"] == 0.14


# ── get_pentest ─────────────────────────────────────────────────────────────

def test_get_pentest_uses_single_record_path(monkeypatch):
    class Client(_FakeAsyncClient):
        async def get(self, url, headers=None):
            assert url == "http://app:5000/service-api/v1/pentests/7"
            return _FakeResponse(200, {"pentest": {"record_id": 7, "scan_status": "idle"}})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    result = asyncio.run(server_module.fetch_service_dataset("/service-api/v1/pentests/7", _settings()))
    assert result["pentest"]["record_id"] == 7
    assert result["pentest"]["scan_status"] == "idle"


# ── set_scan_status ─────────────────────────────────────────────────────────

def test_set_scan_status_sends_correct_body(monkeypatch):
    put_captured: dict = {}

    class Client(_FakeAsyncClient):
        async def put(self, url, json=None, headers=None):
            put_captured["url"] = url
            put_captured["body"] = json
            put_captured["headers"] = headers
            return _FakeResponse(200, {"message": "Scan status updated."})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    asyncio.run(write_tools_module.do_set_scan_status(9, "running", _settings()))
    assert put_captured["url"].endswith("/pentests/9/scan-status")
    assert put_captured["body"] == {"scan_status": "running"}
    assert put_captured["headers"].get("X-RAPTOR-Scanner") == "1"
