from raptor_mcp.settings import (
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_ALLOWED_ORIGINS,
    load_transport_security_hosts,
    load_transport_security_origins,
)


def test_transport_security_defaults(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

    assert load_transport_security_hosts() == DEFAULT_ALLOWED_HOSTS
    assert load_transport_security_origins() == DEFAULT_ALLOWED_ORIGINS


def test_transport_security_merges_public_hosts_and_origins(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "raptor.azercell.com, raptor.azercell.com:443, localhost:*")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://raptor.azercell.com, https://raptor.azercell.com")

    assert load_transport_security_hosts() == (
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
        "raptor.azercell.com",
        "raptor.azercell.com:443",
    )
    assert load_transport_security_origins() == (
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
        "https://raptor.azercell.com",
    )
