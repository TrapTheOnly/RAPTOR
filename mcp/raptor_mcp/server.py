import asyncio
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from raptor_mcp.http_client import fetch_service_dataset
from raptor_mcp.settings import (
    MCPSettings,
    load_settings,
    load_transport_security_hosts,
    load_transport_security_origins,
)
from raptor_mcp.write_tools import (
    do_add_pentest_vulnerability,
    do_get_or_create_vuln_category,
    do_log_scan_event,
    do_notify_scan_complete,
    do_reset_scan,
    do_set_scan_status,
    do_update_checklist_item,
    do_update_pentest_ports,
    mutate_service_dataset,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="raptor-mcp",
    streamable_http_path="/mcp",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(load_transport_security_hosts()),
        allowed_origins=list(load_transport_security_origins()),
    ),
)


@mcp.tool(name="list_records", description="Fetch full records dataset from RAPTOR service API")
async def list_records() -> Any:
    settings = load_settings()
    return await fetch_service_dataset("/service-api/v1/records", settings)


@mcp.tool(name="list_pentests", description="Fetch full pentests dataset from RAPTOR service API")
async def list_pentests() -> Any:
    settings = load_settings()
    return await fetch_service_dataset("/service-api/v1/pentests", settings)


@mcp.tool(
    name="get_pentest",
    description="Fetch a single pentest record by record_id, including current scan_status, ports, checklist state, and vulnerabilities",
)
async def get_pentest(record_id: int) -> Any:
    settings = load_settings()
    return await fetch_service_dataset(f"/service-api/v1/pentests/{record_id}", settings)


@mcp.tool(
    name="set_scan_status",
    description=(
        "Set the scan lifecycle status on a pentest record. "
        "status must be 'idle', 'running', 'completed', or 'failed'."
    ),
)
async def set_scan_status(record_id: int, scan_status: str) -> Any:
    settings = load_settings()
    return await do_set_scan_status(record_id, scan_status, settings)


@mcp.tool(
    name="get_checklist_templates",
    description="Fetch all checklist templates from RAPTOR, including keys, item IDs, and auto-detected ports",
)
async def get_checklist_templates() -> Any:
    settings = load_settings()
    return await fetch_service_dataset("/service-api/v1/checklist-templates", settings)


@mcp.tool(
    name="update_pentest_ports",
    description="Set the open_ports string on a pentest record (comma-separated port numbers, e.g. '22,80,443')",
)
async def update_pentest_ports(record_id: int, open_ports: str) -> Any:
    settings = load_settings()
    return await do_update_pentest_ports(record_id, open_ports, settings)


@mcp.tool(
    name="list_vuln_categories",
    description="List all available vulnerability categories (id and name). Use this before add_pentest_vulnerability to pick or create the right category.",
)
async def list_vuln_categories() -> Any:
    settings = load_settings()
    return await fetch_service_dataset("/service-api/v1/vuln-categories", settings)


@mcp.tool(
    name="get_or_create_vuln_category",
    description=(
        "Look up a vulnerability category by name (case-insensitive). "
        "If it already exists, returns its id. "
        "If it does not exist, creates it and returns the new id. "
        "Always call this before add_pentest_vulnerability to resolve category_id."
    ),
)
async def get_or_create_vuln_category(name: str) -> Any:
    settings = load_settings()
    return await do_get_or_create_vuln_category(name, settings)


@mcp.tool(
    name="add_pentest_vulnerability",
    description=(
        "Append a new vulnerability to a pentest record. "
        "Provide CVSS v3.1 vector metrics individually. "
        "Always resolve category_id first with get_or_create_vuln_category — never pass an empty string. "
        "The description field MUST be a markdown document using this exact template:\n\n"
        "# <Vulnerability Title>\n\n"
        "## Description\n"
        "<What the issue is and why it exists.>\n\n"
        "## Proof of Concept\n"
        "<Step-by-step reproduction or tool output snippet that confirms the issue.>\n\n"
        "## Impact\n"
        "<What an attacker can achieve; business/technical consequence.>\n\n"
        "## Remediation\n"
        "<Specific, actionable fix — not generic advice.>\n\n"
        "All four sections are mandatory. Keep total description under 500 words."
    ),
)
async def add_pentest_vulnerability(
    record_id: int,
    description: str,
    category_id: str,
    av: str,
    ac: str,
    pr: str,
    ui: str,
    s: str,
    c: str,
    i: str,
    a: str,
) -> Any:
    settings = load_settings()
    return await do_add_pentest_vulnerability(
        record_id, description, category_id, av, ac, pr, ui, s, c, i, a, settings
    )


@mcp.tool(
    name="reset_scan",
    description=(
        "Clear all previous scan results for a pentest record before re-running a scan. "
        "Deletes all scan events, clears vulnerabilities, resets checklist_states to empty, "
        "clears open_ports, and sets scan_status back to 'idle'. "
        "Call this ONLY when explicitly restarting a scan from scratch."
    ),
)
async def reset_scan(record_id: int) -> Any:
    settings = load_settings()
    return await do_reset_scan(record_id, settings)


@mcp.tool(
    name="update_checklist_item",
    description=(
        "Set the status of a checklist item on a pentest record. "
        "status must be 'completed', 'irrelevant', or 'unstarted'. "
        "template_key and item_id come from get_checklist_templates."
    ),
)
async def update_checklist_item(record_id: int, template_key: str, item_id: str, status: str) -> Any:
    settings = load_settings()
    return await do_update_checklist_item(record_id, template_key, item_id, status, settings)


@mcp.tool(
    name="log_scan_event",
    description="Record a structured scan progress event (api_call, tool_call, tool_result, finding, status).",
)
async def log_scan_event(record_id: int, event_type: str, payload: dict) -> Any:
    settings = load_settings()
    return await do_log_scan_event(record_id, event_type, payload, settings)


@mcp.tool(
    name="notify_scan_complete",
    description=(
        "Send a scan-completion notification (in-app + email) to the assigned tester and managers. "
        "Include token usage and cost for the scan run."
    ),
)
async def notify_scan_complete(
    record_id: int,
    findings_count: int,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int,
    cache_creation_input_tokens: int,
    cost_usd: float,
) -> Any:
    settings = load_settings()
    return await do_notify_scan_complete(
        record_id,
        findings_count,
        input_tokens,
        output_tokens,
        cache_read_input_tokens,
        cache_creation_input_tokens,
        cost_usd,
        settings,
    )


def run_records_tool_sync(settings: MCPSettings) -> Any:
    return asyncio.run(fetch_service_dataset("/service-api/v1/records", settings))


def run_pentests_tool_sync(settings: MCPSettings) -> Any:
    return asyncio.run(fetch_service_dataset("/service-api/v1/pentests", settings))


__all__ = [
    "add_pentest_vulnerability",
    "fetch_service_dataset",
    "get_checklist_templates",
    "get_or_create_vuln_category",
    "get_pentest",
    "list_pentests",
    "list_records",
    "list_vuln_categories",
    "log_scan_event",
    "mcp",
    "mutate_service_dataset",
    "notify_scan_complete",
    "reset_scan",
    "run_pentests_tool_sync",
    "run_records_tool_sync",
    "set_scan_status",
    "update_checklist_item",
    "update_pentest_ports",
]
