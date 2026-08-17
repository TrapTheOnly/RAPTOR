import os
from dataclasses import dataclass


class SettingsError(ValueError):
    pass


def _require(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise SettingsError(f"{name} is required")
    return value


def _optional(name: str, default: str = "") -> str:
    return str(os.getenv(name) or default).strip()


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError as exc:
        raise SettingsError(f"{name} must be a number") from exc


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class ScanSettings:
    """Per-job settings, derived from the HTTP request body + service env."""
    record_id: int
    aws_region: str
    bedrock_model_id: str
    cost_limit_usd: float
    input_cost_per_1m: float
    output_cost_per_1m: float
    thinking_budget_tokens: int
    proxy_url: str
    proxy_username: str
    proxy_password: str
    mcp_base_url: str
    mcp_server_token: str
    kali_server_url: str
    kali_client_path: str
    allow_destructive_tools: bool


@dataclass(frozen=True)
class ServiceSettings:
    """Container-level settings loaded once at startup from env vars."""
    host: str
    port: int
    scanner_internal_token: str
    mcp_base_url: str
    mcp_server_token: str
    max_concurrent_scans: int
    kali_server_url: str
    kali_client_path: str


def load_service_settings() -> ServiceSettings:
    return ServiceSettings(
        host=_optional("SCANNER_HOST", "0.0.0.0"),
        port=_int_env("SCANNER_PORT", 8082),
        scanner_internal_token=_require("SCANNER_INTERNAL_TOKEN"),
        mcp_base_url=_optional("MCP_BASE_URL", "http://mcp:8081"),
        mcp_server_token=_require("MCP_SERVER_TOKEN"),
        max_concurrent_scans=_int_env("SCANNER_MAX_CONCURRENT", 2),
        kali_server_url=_optional("KALI_SERVER_URL", "http://kali:5000"),
        kali_client_path=_optional("KALI_CLIENT_PATH", "/opt/mcp-kali-server/client.py"),
    )


def build_scan_settings(job: dict, service: ServiceSettings) -> ScanSettings:
    """Validate and build per-job settings from a /scans request body."""
    record_id = job.get("record_id")
    if not isinstance(record_id, int) or record_id <= 0:
        raise SettingsError("record_id must be a positive integer")
    aws_region = str(job.get("aws_region") or "").strip()
    if not aws_region:
        raise SettingsError("aws_region is required")
    bedrock_model_id = str(job.get("bedrock_model_id") or "").strip()
    if not bedrock_model_id:
        raise SettingsError("bedrock_model_id is required")
    cost_limit = float(job.get("cost_limit_usd") or 5.0)
    input_cost = float(job.get("input_cost_per_1m") or 3.0)
    output_cost = float(job.get("output_cost_per_1m") or 15.0)
    thinking_budget = int(job.get("thinking_budget_tokens") or 8000)
    return ScanSettings(
        record_id=record_id,
        aws_region=aws_region,
        bedrock_model_id=bedrock_model_id,
        cost_limit_usd=cost_limit,
        input_cost_per_1m=input_cost,
        output_cost_per_1m=output_cost,
        thinking_budget_tokens=thinking_budget,
        proxy_url=str(job.get("proxy_url") or ""),
        proxy_username=str(job.get("proxy_username") or ""),
        proxy_password=str(job.get("proxy_password") or ""),
        mcp_base_url=service.mcp_base_url,
        mcp_server_token=service.mcp_server_token,
        kali_server_url=service.kali_server_url,
        kali_client_path=service.kali_client_path,
        allow_destructive_tools=bool(job.get("allow_destructive_tools")),
    )


__all__ = [
    "ScanSettings",
    "ServiceSettings",
    "SettingsError",
    "build_scan_settings",
    "load_service_settings",
]
