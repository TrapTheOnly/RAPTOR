from starlette.testclient import TestClient

from raptor_mcp.app import create_app
from raptor_mcp.settings import MCPSettings


def _settings() -> MCPSettings:
    return MCPSettings(
        mcp_server_token="test-token",
        raptor_service_api_key="test-service-key",
        raptor_api_base_url="http://app:5000",
        mcp_port=8081,
        raptor_api_timeout_seconds=30.0,
    )


def test_healthz_is_public():
    app = create_app(_settings())
    client = TestClient(app)

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mcp_endpoint_requires_token():
    app = create_app(_settings())
    client = TestClient(app)

    response = client.post("/mcp", json={})
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized access"}


def test_mcp_endpoint_rejects_invalid_token():
    app = create_app(_settings())
    client = TestClient(app)

    response = client.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_mcp_endpoint_accepts_valid_token():
    app = create_app(_settings())
    client = TestClient(app)

    response = client.post("/mcp", json={}, headers={"Authorization": "Bearer test-token"})
    assert response.status_code != 401
