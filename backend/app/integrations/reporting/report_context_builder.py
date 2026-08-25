"""Build ReportContext for host generate and app/env/wave export sheets."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.integrations.reporting.report_context import (
    FINDINGS_EXPORT_CAP,
    collect_involved_people,
    compute_metrics,
    hash_export_payload,
    normalize_finding,
    stamp_generated_clock,
)
from app.repositories.pentest_findings_repository import CLOSED_OCCURRENCE_STATUSES


def findings_from_packed(packed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings = []
    for raw in packed:
        finding = normalize_finding(raw)
        if finding:
            findings.append(finding)
    return findings


def hosts_from_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {}
    for finding in findings:
        for occ in list(finding.get("occurrences") or []) + list(finding.get("also_observed") or []):
            key = occ.get("record_id") or occ.get("dns")
            if not key or key in seen:
                continue
            seen[key] = {
                "record_id": occ.get("record_id"),
                "dns": occ.get("dns") or "",
                "ip": "",
                "env": occ.get("env") or "",
                "ports": [],
            }
    return list(seen.values())


def build_sheet_context(
    *,
    scope: str,
    package: str,
    app: Dict[str, Any],
    selected_envs: List[Dict[str, Any]],
    packed_findings: List[Dict[str, Any]],
    username: str,
    watermark: str,
    wave: Optional[Dict[str, Any]] = None,
    content_hash: str = "",
    signature: str = "",
    export_id: Any = "",
) -> Dict[str, Any]:
    findings = findings_from_packed(packed_findings)
    hosts = hosts_from_findings(findings)
    metrics, severity_counts, occurrence_counts = compute_metrics(
        findings,
        host_count=len(hosts),
    )
    involved = collect_involved_people({"findings": findings}) or username
    app_name = str(app.get("name") or "")
    wave_payload = {"id": "", "name": ""}
    if wave:
        wave_payload = {"id": wave.get("id") or "", "name": str(wave.get("name") or "")}
    resolved_scope = "wave" if wave_payload.get("id") and package == "wave_archive" else scope
    context = {
        "scope": resolved_scope if resolved_scope in {"host", "environment", "application", "wave"} else "application",
        "package": package,
        "application": {
            "id": app.get("id") or "",
            "name": app_name,
            "roe_link": app.get("roe_link") or "",
        },
        "record": {
            "name": app_name,
            "ip_address": "",
            "source": "",
            "application_name": app_name,
            "description": app.get("roe_link") or "",
        },
        "pentest": {
            "status": "",
            "tested_by": involved,
            "test_start_date": "",
            "test_end_date": "",
            "service_desk_link": "",
            "notes": "",
            "open_ports": "",
            "vulnerable": "Yes" if findings else "No",
            "vulnerability_fixed": "Yes"
            if findings and metrics["open_like_count"] == 0
            else "No",
            "collaborators": involved,
        },
        "wave": wave_payload,
        "environments": [
            {
                "id": env.get("id"),
                "slug": env.get("slug") or "",
                "is_production": bool(env.get("is_production") or env.get("slug") == "prod"),
            }
            for env in selected_envs
        ],
        "hosts": hosts,
        "findings": findings,
        "metrics": metrics,
        "open_ports": [],
        "checklist_states": {},
        "severity_counts": severity_counts,
        "occurrence_counts": occurrence_counts,
        "collaborator_usernames": [part.strip() for part in involved.split(",") if part.strip()],
        "export": {
            "id": export_id or "",
            "watermark": watermark,
            "content_hash": content_hash,
            "signature": signature,
            "generated_at": "",
        },
        "placeholders": {},
        "generated_by": username,
    }
    stamp_generated_clock(context, username)
    return context


def export_cap_error(total: int) -> Optional[Tuple[Dict[str, Any], int]]:
    if int(total or 0) > FINDINGS_EXPORT_CAP:
        return {
            "error": (
                f"Export exceeds {FINDINGS_EXPORT_CAP} findings. "
                "Narrow environments, severity, or wave membership."
            )
        }, 400
    return None


def sheet_content_hash(findings: List[Dict[str, Any]], env_ids: List[int]) -> str:
    return hash_export_payload([item.get("id") for item in findings], env_ids)


def host_content_hash(findings: List[Dict[str, Any]], record_id: int) -> str:
    return hash_export_payload([item.get("id") for item in findings], [record_id])


def closed_occurrence_statuses() -> set:
    return set(CLOSED_OCCURRENCE_STATUSES)


__all__ = [
    "build_sheet_context",
    "export_cap_error",
    "findings_from_packed",
    "host_content_hash",
    "sheet_content_hash",
]
