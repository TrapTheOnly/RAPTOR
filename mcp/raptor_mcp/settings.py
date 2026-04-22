import os
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MCPSettings:
    mcp_server_token: str
    raptor_service_api_key: str
    raptor_api_base_url: str = "http://app:5000"
    mcp_port: int = 8081
    raptor_api_timeout_seconds: float = 30.0
    mcp_allowed_hosts: tuple[str, ...] = ()
    mcp_allowed_origins: tuple[str, ...] = ()


class SettingsError(ValueError):
    """Raised when required MCP settings are missing or invalid."""


def _read_required_env(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise SettingsError(f"{name} is required")
    return value


def _parse_csv_env(name: str) -> tuple[str, ...]:
    raw_value = str(os.getenv(name) or "").strip()
    if not raw_value:
        return ()

    items: list[str] = []
    for item in raw_value.split(","):
        normalized = item.strip()
        if normalized and normalized not in items:
            items.append(normalized)
    return tuple(items)


def _merge_unique(*groups: Iterable[str]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item not in merged:
                merged.append(item)
    return tuple(merged)


def load_settings() -> MCPSettings:
    token = _read_required_env("MCP_SERVER_TOKEN")
    service_key = _read_required_env("RAPTOR_SERVICE_API_KEY")

    api_base = str(os.getenv("RAPTOR_API_BASE_URL") or "http://app:5000").strip() or "http://app:5000"

    port_value = str(os.getenv("MCP_PORT") or "8081").strip()
    timeout_value = str(os.getenv("RAPTOR_API_TIMEOUT_SECONDS") or "30").strip()

    try:
        mcp_port = int(port_value)
    except ValueError as exc:
        raise SettingsError("MCP_PORT must be an integer") from exc

    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise SettingsError("RAPTOR_API_TIMEOUT_SECONDS must be a number") from exc

    if mcp_port <= 0 or mcp_port > 65535:
        raise SettingsError("MCP_PORT must be in range 1..65535")
    if timeout_seconds <= 0:
        raise SettingsError("RAPTOR_API_TIMEOUT_SECONDS must be greater than 0")

    return MCPSettings(
        mcp_server_token=token,
        raptor_service_api_key=service_key,
        raptor_api_base_url=api_base.rstrip("/"),
        mcp_port=mcp_port,
        raptor_api_timeout_seconds=timeout_seconds,
        mcp_allowed_hosts=_parse_csv_env("MCP_ALLOWED_HOSTS"),
        mcp_allowed_origins=_parse_csv_env("MCP_ALLOWED_ORIGINS"),
    )

DEFAULT_ALLOWED_HOSTS = ("127.0.0.1:*", "localhost:*", "[::1]:*", "mcp:*")
DEFAULT_ALLOWED_ORIGINS = ("http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*")


def load_transport_security_hosts() -> tuple[str, ...]:
    return _merge_unique(DEFAULT_ALLOWED_HOSTS, _parse_csv_env("MCP_ALLOWED_HOSTS"))


def load_transport_security_origins() -> tuple[str, ...]:
    return _merge_unique(DEFAULT_ALLOWED_ORIGINS, _parse_csv_env("MCP_ALLOWED_ORIGINS"))


__all__ = [
    "DEFAULT_ALLOWED_HOSTS",
    "DEFAULT_ALLOWED_ORIGINS",
    "MCPSettings",
    "SettingsError",
    "load_settings",
    "load_transport_security_hosts",
    "load_transport_security_origins",
]
