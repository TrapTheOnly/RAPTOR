import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MCPSettings:
    mcp_server_token: str
    raptor_service_api_key: str
    raptor_api_base_url: str = "http://app:5000"
    mcp_port: int = 8081
    raptor_api_timeout_seconds: float = 30.0


class SettingsError(ValueError):
    """Raised when required MCP settings are missing or invalid."""


def _read_required_env(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise SettingsError(f"{name} is required")
    return value


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
    )


__all__ = ["MCPSettings", "SettingsError", "load_settings"]
