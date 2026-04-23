import json
import logging
import time
from json import JSONDecodeError
from typing import Any

import httpx

from raptor_mcp.http_client import fetch_service_dataset
from raptor_mcp.settings import MCPSettings, load_settings

logger = logging.getLogger(__name__)

# CVSS v3.1 metric weights
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.5}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"N": 0.0, "L": 0.22, "H": 0.56}

VALID_CHECKLIST_STATUSES = {"completed", "irrelevant", "unstarted"}


def _calculate_cvss_base(metrics: dict) -> float:
    av = _AV.get(metrics.get("AV", "N"), 0.85)
    ac = _AC.get(metrics.get("AC", "L"), 0.77)
    scope_changed = metrics.get("S", "U") == "C"
    pr = (_PR_C if scope_changed else _PR_U).get(metrics.get("PR", "N"), 0.85)
    ui = _UI.get(metrics.get("UI", "N"), 0.85)
    c = _CIA.get(metrics.get("C", "N"), 0.0)
    i = _CIA.get(metrics.get("I", "N"), 0.0)
    a = _CIA.get(metrics.get("A", "N"), 0.0)

    iss = 1 - (1 - c) * (1 - i) * (1 - a)
    if iss == 0:
        return 0.0

    if scope_changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)
    else:
        impact = 6.42 * iss

    exploitability = 8.22 * av * ac * pr * ui

    if scope_changed:
        base = min(1.08 * (impact + exploitability), 10)
    else:
        base = min(impact + exploitability, 10)

    return round(base * 10) / 10


def _sanitize_upstream_error(response: httpx.Response) -> str:
    from raptor_mcp.http_client import _sanitize_upstream_error as _base
    return _base(response)


async def mutate_service_dataset(method: str, path: str, body: dict, settings: MCPSettings) -> Any:
    url = f"{settings.raptor_api_base_url}{path}"
    timeout = httpx.Timeout(settings.raptor_api_timeout_seconds)
    headers = {
        "X-API-Key": settings.raptor_service_api_key,
        "X-RAPTOR-Scanner": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await getattr(client, method)(url, json=body, headers=headers)
    except httpx.TimeoutException as exc:
        raise RuntimeError("RAPTOR API request timed out. Retry later.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Failed to connect to RAPTOR API. Retry later.") from exc

    if response.status_code >= 400:
        error_text = _sanitize_upstream_error(response)
        raise RuntimeError(f"RAPTOR API error ({response.status_code}): {error_text}")

    try:
        return response.json()
    except JSONDecodeError as exc:
        raise RuntimeError("RAPTOR API returned a non-JSON response.") from exc


async def do_set_scan_status(record_id: int, scan_status: str, settings: MCPSettings) -> Any:
    return await mutate_service_dataset(
        "put",
        f"/service-api/v1/pentests/{record_id}/scan-status",
        {"scan_status": scan_status},
        settings,
    )


async def do_update_pentest_ports(record_id: int, open_ports: str, settings: MCPSettings) -> Any:
    return await mutate_service_dataset(
        "patch",
        f"/service-api/v1/pentests/{record_id}",
        {"open_ports": open_ports},
        settings,
    )


async def do_add_pentest_vulnerability(
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
    settings: MCPSettings,
) -> Any:
    metrics = {"AV": av, "AC": ac, "PR": pr, "UI": ui, "S": s, "C": c, "I": i, "A": a}
    base_score = _calculate_cvss_base(metrics)
    vulnerability = {
        "id": int(time.time() * 1000),
        "categoryId": category_id,
        "description": description,
        "created_by": "RAPTOR-Scanner",
        "metrics": metrics,
        "baseScore": base_score,
    }
    return await mutate_service_dataset(
        "post",
        f"/service-api/v1/pentests/{record_id}/vulnerabilities",
        vulnerability,
        settings,
    )


async def do_update_checklist_item(
    record_id: int,
    template_key: str,
    item_id: str,
    status: str,
    settings: MCPSettings,
) -> Any:
    if status not in VALID_CHECKLIST_STATUSES:
        raise ValueError(f"status must be one of: {sorted(VALID_CHECKLIST_STATUSES)}")

    pentest_payload = await fetch_service_dataset(f"/service-api/v1/pentests/{record_id}", settings)
    pentest = pentest_payload.get("pentest", {}) if isinstance(pentest_payload, dict) else {}

    checklist_states: dict = {"selected": [], "statuses": {}}
    raw = pentest.get("checklist_states") or "{}"
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, dict):
            checklist_states = parsed
    except (json.JSONDecodeError, TypeError):
        pass

    selected = list(checklist_states.get("selected") or [])
    if template_key not in selected:
        selected.append(template_key)

    statuses = dict(checklist_states.get("statuses") or {})
    template_statuses_raw = statuses.get(template_key)
    template_statuses = dict(template_statuses_raw) if isinstance(template_statuses_raw, dict) else {}
    template_statuses[item_id] = status
    statuses[template_key] = template_statuses

    updated_states = {"selected": selected, "statuses": statuses}
    return await mutate_service_dataset(
        "patch",
        f"/service-api/v1/pentests/{record_id}",
        {"checklist_states": json.dumps(updated_states)},
        settings,
    )


async def do_log_scan_event(
    record_id: int,
    event_type: str,
    payload: dict,
    settings: MCPSettings,
) -> Any:
    return await mutate_service_dataset(
        "post",
        f"/service-api/v1/pentests/{record_id}/scan-events",
        {"event_type": event_type, "payload": payload},
        settings,
    )


async def do_notify_scan_complete(
    record_id: int,
    findings_count: int,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int,
    cache_creation_input_tokens: int,
    cost_usd: float,
    settings: MCPSettings,
) -> Any:
    return await mutate_service_dataset(
        "post",
        f"/service-api/v1/pentests/{record_id}/notify-scan-complete",
        {
            "findings_count": findings_count,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cost_usd": cost_usd,
        },
        settings,
    )


async def do_get_or_create_vuln_category(name: str, settings: MCPSettings) -> Any:
    name = name.strip()
    if not name:
        raise ValueError("Category name must not be empty.")
    categories_payload = await fetch_service_dataset("/service-api/v1/vuln-categories", settings)
    categories = categories_payload.get("categories", []) if isinstance(categories_payload, dict) else []
    name_lower = name.lower()
    for cat in categories:
        if str(cat.get("name") or "").lower() == name_lower:
            return {"id": cat["id"], "name": cat["name"], "created": False}
    result = await mutate_service_dataset(
        "post",
        "/service-api/v1/vuln-categories",
        {"name": name},
        settings,
    )
    return {"id": result.get("id"), "name": name, "created": True}


async def do_reset_scan(record_id: int, settings: MCPSettings) -> Any:
    return await mutate_service_dataset(
        "post",
        f"/service-api/v1/pentests/{record_id}/reset-scan",
        {},
        settings,
    )


__all__ = [
    "VALID_CHECKLIST_STATUSES",
    "_calculate_cvss_base",
    "do_add_pentest_vulnerability",
    "do_get_or_create_vuln_category",
    "do_log_scan_event",
    "do_notify_scan_complete",
    "do_reset_scan",
    "do_set_scan_status",
    "do_update_checklist_item",
    "do_update_pentest_ports",
    "mutate_service_dataset",
]
