import os
from dataclasses import dataclass
from typing import Any, Tuple


class SettingsError(ValueError):
    pass


def _require(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise SettingsError(f"{name} is required")
    return value


def _optional(name: str, default: str = "") -> str:
    return str(os.getenv(name) or default).strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer") from exc


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass(frozen=True)
class ScanSettings:
    """Per-job settings, derived from the HTTP request body + service env."""
    record_id: int
    provider_type: str
    provider_display_name: str
    protocol: str
    base_url: str
    api_key: str
    model_id: str
    aws_region: str
    aws_access_key: str
    aws_secret_key: str
    aws_session_token: str
    aws_bearer_token: str
    azure_api_version: str
    extra_headers: dict[str, Any]
    project_ocid: str
    cost_limit_usd: float
    input_cost_per_1m: float
    output_cost_per_1m: float
    thinking_budget_tokens: int
    max_turns: int
    proxy_url: str
    proxy_username: str
    proxy_password: str
    mcp_base_url: str
    mcp_server_token: str
    kali_server_url: str
    kali_client_path: str
    allow_destructive_tools: bool
    record_ids: Tuple[int, ...]
    hosts: Tuple[dict[str, Any], ...]
    wave_id: int
    job_id: int
    operator_brief: str
    skip_port_discovery: bool


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


def _record_ids_from_job(job: dict) -> list[int]:
    raw_ids = job.get("record_ids")
    ids: list[int] = []
    if isinstance(raw_ids, list):
        for item in raw_ids:
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            if value > 0:
                ids.append(value)
    record_id = job.get("record_id")
    if isinstance(record_id, int) and record_id > 0 and record_id not in ids:
        ids.insert(0, record_id)
    return ids


def _hosts_from_job(job: dict, record_ids: list[int]) -> tuple[dict[str, Any], ...]:
    raw_hosts = job.get("hosts")
    hosts: list[dict[str, Any]] = []
    if isinstance(raw_hosts, list):
        for item in raw_hosts:
            if not isinstance(item, dict):
                continue
            try:
                record_id = int(item.get("record_id") or 0)
            except (TypeError, ValueError):
                continue
            if record_id <= 0:
                continue
            hosts.append({
                "record_id": record_id,
                "name": str(item.get("name") or ""),
                "ip_address": str(item.get("ip_address") or ""),
            })
    known = {host["record_id"] for host in hosts}
    for record_id in record_ids:
        if record_id not in known:
            hosts.append({"record_id": record_id, "name": "", "ip_address": ""})
    return tuple(hosts)


def build_scan_settings(job: dict, service: ServiceSettings) -> ScanSettings:
    """Validate and build per-job settings from a /scans request body."""
    record_ids = _record_ids_from_job(job)
    if not record_ids:
        raise SettingsError("record_id or record_ids must include a positive integer")
    record_id = record_ids[0]
    hosts = _hosts_from_job(job, record_ids)
    model_id = str(job.get("model_id") or job.get("bedrock_model_id") or "").strip()
    if not model_id:
        raise SettingsError("model_id is required")
    protocol = str(job.get("protocol") or "").strip().lower()
    provider_type = str(job.get("provider_type") or "").strip().lower()
    if not provider_type:
        provider_type = "bedrock" if job.get("bedrock_model_id") else protocol
    if not protocol:
        protocol = "anthropic" if provider_type in {"anthropic", "bedrock", "anthropic_compat"} else "openai"
    if protocol not in {"anthropic", "openai"}:
        raise SettingsError("protocol must be anthropic or openai")
    cost_limit = float(job.get("cost_limit_usd") or 5.0)
    input_cost = float(job.get("input_cost_per_1m") or 0.0)
    output_cost = float(job.get("output_cost_per_1m") or 0.0)
    thinking_budget = int(job.get("thinking_budget_tokens") or 8000)
    max_turns = int(job.get("max_turns") or 40)
    if max_turns < 1:
        raise SettingsError("max_turns must be at least 1")
    operator_brief = str(job.get("operator_brief") or job.get("details") or "").strip()[:4000]
    return ScanSettings(
        record_id=record_id,
        provider_type=provider_type,
        provider_display_name=str(job.get("provider_display_name") or provider_type),
        protocol=protocol,
        base_url=str(job.get("base_url") or ""),
        api_key=str(job.get("api_key") or ""),
        model_id=model_id,
        aws_region=str(job.get("aws_region") or "us-east-1"),
        aws_access_key=str(job.get("aws_access_key") or ""),
        aws_secret_key=str(job.get("aws_secret_key") or ""),
        aws_session_token=str(job.get("aws_session_token") or ""),
        aws_bearer_token=str(job.get("aws_bearer_token") or job.get("api_key") or ""),
        azure_api_version=str(job.get("azure_api_version") or "2024-10-21"),
        extra_headers=_as_dict(job.get("extra_headers")),
        project_ocid=str(job.get("project_ocid") or ""),
        cost_limit_usd=cost_limit,
        input_cost_per_1m=input_cost,
        output_cost_per_1m=output_cost,
        thinking_budget_tokens=thinking_budget,
        max_turns=max_turns,
        proxy_url=str(job.get("proxy_url") or ""),
        proxy_username=str(job.get("proxy_username") or ""),
        proxy_password=str(job.get("proxy_password") or ""),
        mcp_base_url=service.mcp_base_url,
        mcp_server_token=service.mcp_server_token,
        kali_server_url=service.kali_server_url,
        kali_client_path=service.kali_client_path,
        allow_destructive_tools=bool(job.get("allow_destructive_tools")),
        record_ids=tuple(record_ids),
        hosts=hosts,
        wave_id=int(job.get("wave_id") or 0),
        job_id=int(job.get("job_id") or 0),
        operator_brief=operator_brief,
        skip_port_discovery=bool(job.get("skip_port_discovery")),
    )


__all__ = [
    "ScanSettings",
    "ServiceSettings",
    "SettingsError",
    "build_scan_settings",
    "load_service_settings",
]
