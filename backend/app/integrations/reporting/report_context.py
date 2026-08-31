"""Typed report envelope shared by host generate and app/env/wave exports."""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.integrations.reporting.report_pdf_model import (
    PLACEHOLDER_PATTERN,
    flatten,
    parse_open_ports,
    safe_json_load,
    severity_from_score,
    to_float,
    to_int,
)
from app.repositories.pentest_findings_repository import (
    CLOSED_OCCURRENCE_STATUSES,
    OPEN_LIKE_STATUSES,
)

SCOPES = ("host", "environment", "application", "wave")
PACKAGES = ("owner_delivery", "wave_archive", "retest_pack", "internal_draft", "host")
BLOCK_TYPES = {
    "cover",
    "engagement_overview",
    "key_metrics",
    "table_of_contents",
    "chart",
    "open_ports",
    "markdown",
    "checklists",
    "vulnerabilities",
    "text",
    "page_break",
}
CHART_IDS = {
    "vulnerability_severity",
    "occurrence_status",
    "checklist_completion",
    "severity_by_env",
    "wave_coverage",
    "vulnerability_fix_status",
}
DROP_BLOCK_KEYS = {"layout", "_uiId", "_libraryItemKey"}
FINDINGS_EXPORT_CAP = 200
PRINT_INK_DEFAULT = "#067A8A"
PRINT_INK_FALLBACK = "#1E293B"

SEVERITY_PRINT_HEX = {
    "Critical": "#C6262E",
    "High": "#9A4A08",
    "Medium": "#7A5B12",
    "Low": "#5A6472",
    "Informational": "#6A727E",
}

# Filled TOC / table cells: red, orange, yellow, green, blue.
SEVERITY_CELL_HEX = {
    "Critical": ("#DC2626", "#FFFFFF"),
    "High": ("#EA580C", "#FFFFFF"),
    "Medium": ("#EAB308", "#111827"),
    "Low": ("#16A34A", "#FFFFFF"),
    "Informational": ("#2563EB", "#FFFFFF"),
}

STATUS_GLYPHS = {
    "open": "\u25cf",
    "draft": "\u25cb",
    "retest": "\u25d0",
    "fixed": "\u2713",
    "accepted": "\u25cb",
    "not_affected": "\u2298",
}

STATUS_LABELS = {
    "open": "Open",
    "draft": "Draft",
    "retest": "Retest",
    "fixed": "Fixed",
    "accepted": "Accepted",
    "not_affected": "Not affected",
}


class UnknownTokenError(ValueError):
    """A template referenced a token that is not in the registry."""


class UnknownChartError(ValueError):
    """A chart block named a type that is not in the closed catalog."""


class UnknownBlockError(ValueError):
    """A template used a block type the renderer does not implement."""


def _blank_metrics() -> Dict[str, Any]:
    return {
        "vulnerability_count": 0,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "informational_count": 0,
        "critical_high_count": 0,
        "open_findings": 0,
        "fixed_findings": 0,
        "open_like_count": 0,
        "closed_count": 0,
        "occurrence_open": 0,
        "occurrence_draft": 0,
        "occurrence_retest": 0,
        "occurrence_fixed": 0,
        "occurrence_accepted": 0,
        "occurrence_not_affected": 0,
        "open_ports_count": 0,
        "host_count": 0,
        "checklist_total": 0,
        "checklist_completed": 0,
        "checklist_irrelevant": 0,
        "checklist_unstarted": 0,
        "checklist_percentage": 0,
    }


def empty_token_context() -> Dict[str, Any]:
    return {
        "scope": "",
        "package": "",
        "generated_at": "",
        "generated_date": "",
        "generated_by": "",
        "application": {"id": "", "name": "", "roe_link": ""},
        "record": {
            "name": "",
            "ip_address": "",
            "source": "",
            "application_name": "",
            "description": "",
        },
        "pentest": {
            "status": "",
            "tested_by": "",
            "test_start_date": "",
            "test_end_date": "",
            "service_desk_link": "",
            "notes": "",
            "open_ports": "",
            "vulnerable": "",
            "vulnerability_fixed": "",
            "collaborators": "",
        },
        "wave": {"id": "", "name": ""},
        "metrics": _blank_metrics(),
        "export": {
            "id": "",
            "watermark": "",
            "content_hash": "",
            "signature": "",
            "generated_at": "",
        },
        "placeholders": {
            "report_title": "",
            "report_subtitle": "",
            "prepared_by": "",
            "prepared_for": "",
        },
    }


def _token_keys() -> set:
    flat: Dict[str, Any] = {}
    flatten("", empty_token_context(), flat)
    keys = set(flat.keys())
    keys.update({"report_title", "report_subtitle", "prepared_by", "prepared_for"})
    return keys


TOKEN_REGISTRY = _token_keys()


def collect_template_tokens(template_definition: Dict[str, Any]) -> List[str]:
    found: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            for match in PLACEHOLDER_PATTERN.finditer(value):
                found.append(match.group(1).strip())
        elif isinstance(value, dict):
            for inner in value.values():
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(template_definition)
    return found


def lint_template_tokens(template_definition: Dict[str, Any]) -> Optional[str]:
    unknown = sorted({token for token in collect_template_tokens(template_definition) if token not in TOKEN_REGISTRY})
    if unknown:
        return f"Unknown template token(s): {', '.join(unknown)}."
    return None


def resolve_placeholders_strict(value: Any, flat_context: Dict[str, Any]) -> Any:
    if not isinstance(value, str):
        return value

    def repl(match: re.Match) -> str:
        key = match.group(1).strip()
        if key not in TOKEN_REGISTRY:
            raise UnknownTokenError(f"Unknown template token: {{{{{key}}}}}")
        return "" if flat_context.get(key) is None else str(flat_context.get(key, ""))

    return PLACEHOLDER_PATTERN.sub(repl, value)


def normalize_occurrence(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    status = str(raw.get("status") or "open").strip().lower() or "open"
    return {
        "record_id": raw.get("record_id"),
        "dns": str(raw.get("dns") or raw.get("dns_name") or "").strip(),
        "env": str(raw.get("env") or raw.get("environment_slug") or "").strip(),
        "env_name": str(raw.get("env_name") or raw.get("environment_name") or "").strip(),
        "status": status,
        "is_production": bool(raw.get("is_production")),
        "evidence_note": str(raw.get("evidence_note") or "").strip(),
    }


def _string_list(raw: Any) -> List[str]:
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def collect_involved_people(
    context: Optional[Dict[str, Any]] = None,
    findings: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    names: List[str] = []
    seen = set()

    def add(raw: Any) -> None:
        for name in _string_list(raw):
            key = name.lower()
            if key in {"unassigned", "n/a"} or key in seen:
                continue
            seen.add(key)
            names.append(name)

    payload = context if isinstance(context, dict) else {}
    pentest = payload.get("pentest") if isinstance(payload.get("pentest"), dict) else {}
    add(pentest.get("tested_by"))
    add(pentest.get("collaborators"))
    add(payload.get("collaborator_usernames"))
    for finding in findings if findings is not None else payload.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        add(finding.get("created_by"))
        add(finding.get("collaborators"))
    return ", ".join(names)


_META_LINE_RE = re.compile(
    r"^\s*(?:\*\*)?(?:host|wave|auth(?:entication)?\s+context)(?:\*\*)?\s*:",
    re.IGNORECASE,
)
_SECTION_HEAD_RE = re.compile(
    r"^\s*(?:#{1,6}\s+|\*\*)(impact|evidence|remediation|description|proof of concept|proof-of-concept|poc)(?:\*\*)?\s*$",
    re.IGNORECASE,
)
_SECTION_ALIASES = {
    "impact": "impact",
    "evidence": "evidence",
    "remediation": "remediation",
    "description": "description",
    "proof of concept": "evidence",
    "proof-of-concept": "evidence",
    "poc": "evidence",
}
_LEADING_TITLE_RE = re.compile(r"^#\s+(.+)$")


def strip_leading_title(text: str) -> Tuple[str, str]:
    """Pull a markdown H1 off the top of a description blob."""
    lines = str(text or "").splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return "", str(text or "").strip()
    match = _LEADING_TITLE_RE.match(lines[index].strip())
    if not match:
        return "", str(text or "").strip()
    title = match.group(1).strip()
    rest = "\n".join(lines[:index] + lines[index + 1 :]).strip()
    return title, rest


def split_finding_narrative(finding: Dict[str, Any]) -> Tuple[str, str, str, str]:
    stored = {
        "impact": str(finding.get("impact") or "").strip(),
        "evidence": str(finding.get("evidence") or "").strip(),
        "remediation": str(finding.get("remediation") or "").strip(),
    }
    buckets = {"description": [], "impact": [], "evidence": [], "remediation": []}
    current = "description"
    for raw_line in str(finding.get("description") or "").splitlines():
        stripped = raw_line.strip()
        if _META_LINE_RE.match(stripped):
            continue
        heading = _SECTION_HEAD_RE.match(stripped)
        if heading:
            current = _SECTION_ALIASES.get(heading.group(1).lower(), "description")
            continue
        buckets[current].append(raw_line)

    def joined(key: str) -> str:
        return "\n".join(buckets[key]).strip()

    description = joined("description")
    impact = stored["impact"] or joined("impact")
    evidence = stored["evidence"] or joined("evidence")
    remediation = stored["remediation"] or joined("remediation")
    extra_notes = []
    for occ in list(finding.get("occurrences") or []) + list(finding.get("also_observed") or []):
        if not isinstance(occ, dict):
            continue
        note = str(occ.get("evidence_note") or "").strip()
        if not note:
            continue
        host = str(occ.get("dns") or occ.get("dns_name") or "").strip()
        extra_notes.append(f"{host}: {note}" if host else note)
    if extra_notes:
        extras = "\n".join(extra_notes)
        evidence = f"{evidence}\n\n{extras}".strip() if evidence else extras
    return description, impact, evidence, remediation


def hydrate_finding_fields(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Move a tutorial-style description blob into RAPTOR's separate columns."""
    out = dict(finding or {})
    description, impact, evidence, remediation = split_finding_narrative(out)
    extracted_title, description = strip_leading_title(description)
    if extracted_title and not str(out.get("title") or "").strip():
        out["title"] = extracted_title
    out["description"] = description
    if not str(out.get("impact") or "").strip():
        out["impact"] = impact
    if not str(out.get("evidence") or "").strip():
        out["evidence"] = evidence
    if not str(out.get("remediation") or "").strip():
        out["remediation"] = remediation
    return out


def normalize_finding(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    occurrences = []
    for item in raw.get("occurrences") or []:
        occ = normalize_occurrence(item)
        if occ:
            occurrences.append(occ)
    also_observed = []
    for item in raw.get("also_observed") or []:
        occ = normalize_occurrence(item)
        if occ:
            also_observed.append(occ)
    title = str(raw.get("title") or raw.get("categoryName") or "").strip()
    category = str(raw.get("category") or raw.get("categoryName") or "").strip()
    return {
        "id": raw.get("id"),
        "title": title or category or "Finding",
        "category": category,
        "description": str(raw.get("description") or ""),
        "impact": str(raw.get("impact") or ""),
        "evidence": str(raw.get("evidence") or ""),
        "remediation": str(raw.get("remediation") or ""),
        "created_by": str(raw.get("created_by") or "").strip(),
        "collaborators": _string_list(raw.get("collaborators")),
        "baseScore": to_float(raw.get("baseScore") or raw.get("base_score"), 0.0),
        "metrics": raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {},
        "status": str(raw.get("status") or "open").strip().lower(),
        "ticket_url": str(raw.get("ticket_url") or ""),
        "occurrences": occurrences,
        "also_observed": also_observed,
    }


def compute_metrics(
    findings: Sequence[Dict[str, Any]],
    *,
    open_ports_count: int = 0,
    host_count: int = 0,
    checklist: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metrics = _blank_metrics()
    severity_counts = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
        "Informational": 0,
    }
    occurrence_counts = {key: 0 for key in STATUS_LABELS}
    for finding in findings:
        severity_counts[severity_from_score(finding.get("baseScore"))] += 1
        rows = finding.get("occurrences") or []
        if not rows:
            status = str(finding.get("status") or "open").strip().lower()
            if status in occurrence_counts:
                occurrence_counts[status] += 1
            continue
        for occ in rows:
            status = str(occ.get("status") or "open").strip().lower()
            if status in occurrence_counts:
                occurrence_counts[status] += 1

    open_like = sum(occurrence_counts[key] for key in OPEN_LIKE_STATUSES if key in occurrence_counts)
    closed = sum(occurrence_counts[key] for key in CLOSED_OCCURRENCE_STATUSES if key in occurrence_counts)
    metrics.update(
        {
            "vulnerability_count": len(findings),
            "critical_count": severity_counts["Critical"],
            "high_count": severity_counts["High"],
            "medium_count": severity_counts["Medium"],
            "low_count": severity_counts["Low"],
            "informational_count": severity_counts["Informational"],
            "critical_high_count": severity_counts["Critical"] + severity_counts["High"],
            "open_findings": open_like,
            "fixed_findings": occurrence_counts.get("fixed", 0),
            "open_like_count": open_like,
            "closed_count": closed,
            "occurrence_open": occurrence_counts.get("open", 0),
            "occurrence_draft": occurrence_counts.get("draft", 0),
            "occurrence_retest": occurrence_counts.get("retest", 0),
            "occurrence_fixed": occurrence_counts.get("fixed", 0),
            "occurrence_accepted": occurrence_counts.get("accepted", 0),
            "occurrence_not_affected": occurrence_counts.get("not_affected", 0),
            "open_ports_count": int(open_ports_count or 0),
            "host_count": int(host_count or 0),
        }
    )
    if checklist:
        metrics.update(checklist)
    return metrics, severity_counts, occurrence_counts


def hash_export_payload(finding_ids: Iterable[Any], env_ids: Iterable[Any]) -> str:
    payload = {
        "findings": [str(item) for item in finding_ids],
        "envs": [int(item) for item in env_ids],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def format_report_date(moment: Optional[datetime.datetime] = None) -> str:
    now = moment or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    return f"{now.day} {now.strftime('%B')} {now.year}"


def stamp_generated_clock(context: Dict[str, Any], generated_by: Optional[str] = None) -> None:
    generated_at = format_report_date()
    context["generated_at"] = generated_at
    context["generated_date"] = generated_at
    if generated_by:
        context["generated_by"] = generated_by
    export = context.setdefault("export", {})
    export["generated_at"] = generated_at


def token_flat_context(context: Dict[str, Any]) -> Dict[str, Any]:
    projection = empty_token_context()
    for key in (
        "scope",
        "package",
        "generated_at",
        "generated_date",
        "generated_by",
        "application",
        "record",
        "pentest",
        "wave",
        "metrics",
        "export",
        "placeholders",
    ):
        if key in context and context[key] is not None:
            projection[key] = context[key]
    flat: Dict[str, Any] = {}
    flatten("", projection, flat)
    placeholders = projection.get("placeholders") if isinstance(projection.get("placeholders"), dict) else {}
    for key, value in placeholders.items():
        flat[str(key)] = "" if value is None else str(value)
        flat[f"placeholders.{key}"] = flat[str(key)]
    return flat


def severity_by_env_counts(findings: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    by_env: Dict[str, Dict[str, int]] = {}
    for finding in findings:
        severity = severity_from_score(finding.get("baseScore"))
        envs = {str(occ.get("env") or "unknown") for occ in (finding.get("occurrences") or [])}
        if not envs:
            envs = {"host"}
        for env in envs:
            bucket = by_env.setdefault(
                env,
                {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Informational": 0},
            )
            bucket[severity] += 1
    return by_env


def context_from_host_record(record_data: Dict[str, Any], generated_by: Optional[str] = None) -> Dict[str, Any]:
    """Adapt a host pentest payload (or a test fixture) into ReportContext."""
    vulnerabilities = safe_json_load(record_data.get("vulnerabilities"), [])
    if not isinstance(vulnerabilities, list):
        vulnerabilities = []
    findings = []
    host_name = str(record_data.get("name") or "")
    host_env = str(record_data.get("environment_slug") or "")
    for raw in vulnerabilities:
        if not isinstance(raw, dict):
            continue
        finding = normalize_finding(raw)
        if not finding:
            continue
        if not finding["occurrences"]:
            finding["occurrences"] = [
                normalize_occurrence(
                    {
                        "record_id": record_data.get("id") or record_data.get("record_id"),
                        "dns_name": host_name,
                        "environment_slug": host_env or "host",
                        "status": finding.get("status") or "open",
                    }
                )
            ]
        findings.append(finding)

    open_ports = parse_open_ports(record_data.get("open_ports"))
    collaborators = record_data.get("collaborators") or []
    if not isinstance(collaborators, list):
        collaborators = []
    collaborator_usernames = [str(item).strip() for item in collaborators if str(item).strip()]
    assignee = record_data.get("tested_by") or "Unassigned"
    app_name = str(record_data.get("application_name") or "")
    metrics, severity_counts, occurrence_counts = compute_metrics(
        findings,
        open_ports_count=len(open_ports),
        host_count=1 if host_name else 0,
    )
    context = {
        "scope": "host",
        "package": "host",
        "application": {
            "id": record_data.get("application_id") or "",
            "name": app_name,
            "roe_link": "",
        },
        "record": {
            "name": host_name,
            "ip_address": record_data.get("ip_address") or "",
            "source": record_data.get("source") or "",
            "application_name": app_name,
            "description": record_data.get("description") or "",
        },
        "pentest": {
            "status": record_data.get("status") or "Not Started",
            "tested_by": assignee,
            "test_start_date": record_data.get("test_start_date") or "",
            "test_end_date": record_data.get("test_end_date") or "",
            "service_desk_link": record_data.get("service_desk_link") or "",
            "notes": record_data.get("notes") or "",
            "open_ports": ", ".join(str(port) for port in open_ports),
            "vulnerable": "Yes" if findings else "No",
            "vulnerability_fixed": "Yes" if metrics["open_like_count"] == 0 and findings else "No",
            "collaborators": ", ".join(collaborator_usernames),
        },
        "wave": {"id": "", "name": ""},
        "environments": [],
        "hosts": [
            {
                "record_id": record_data.get("id") or record_data.get("record_id"),
                "dns": host_name,
                "ip": record_data.get("ip_address") or "",
                "env": host_env,
                "ports": open_ports,
            }
        ]
        if host_name
        else [],
        "findings": findings,
        "metrics": metrics,
        "checklist_states": safe_json_load(record_data.get("checklist_states"), {}),
        "open_ports": open_ports,
        "severity_counts": severity_counts,
        "occurrence_counts": occurrence_counts,
        "collaborator_usernames": collaborator_usernames,
        "export": {
            "id": "",
            "watermark": "",
            "content_hash": "",
            "signature": "",
            "generated_at": "",
        },
        "placeholders": {},
        "generated_by": generated_by or assignee,
    }
    involved = collect_involved_people(context, findings) or assignee
    context["pentest"]["tested_by"] = involved
    stamp_generated_clock(context, generated_by or assignee)
    return context


def coerce_report_context(payload: Optional[Dict[str, Any]], generated_by: Optional[str] = None) -> Dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    if data.get("scope") in SCOPES and "findings" in data:
        context = dict(data)
        stamp_generated_clock(context, generated_by or context.get("generated_by"))
        if generated_by:
            context["generated_by"] = generated_by
        return context
    return context_from_host_record(data, generated_by=generated_by)


def sample_report_context(kind: str = "application") -> Dict[str, Any]:
    """Frozen envelopes for the paper preview. kind is a scope or package key."""
    findings = [
        {
            "id": "f-crit",
            "title": "Stored XSS on checkout",
            "category": "Cross-Site Scripting",
            "description": "User input is reflected without encoding.",
            "impact": "An unauthenticated visitor can run script in a checkout operator session.",
            "evidence": "Stored payload executes on `/checkout/review`.",
            "remediation": "Encode output and set a strict CSP on checkout.",
            "created_by": "alice",
            "collaborators": ["bob"],
            "baseScore": 9.1,
            "metrics": {"AV": "N", "AC": "L", "PR": "N", "UI": "R", "S": "C", "C": "H", "I": "L", "A": "N"},
            "status": "open",
            "occurrences": [
                {"dns_name": "pay.example.com", "environment_slug": "prod", "status": "open", "is_production": True},
                {"dns_name": "pay.stg.example.com", "environment_slug": "stg", "status": "retest"},
            ],
            "also_observed": [
                {"dns_name": "pay.qa.example.com", "environment_slug": "qa", "status": "open"},
            ],
        },
        {
            "id": "f-high",
            "title": "Missing SPF",
            "category": "Email Security",
            "description": "No SPF record for the production zone.",
            "impact": "Callers can spoof mail from the production domain.",
            "evidence": "Published TXT records omit v=spf1.",
            "remediation": "Publish SPF and DMARC, then retest.",
            "created_by": "carol",
            "baseScore": 7.4,
            "status": "retest",
            "occurrences": [
                {"dns_name": "pay.example.com", "environment_slug": "prod", "status": "retest", "is_production": True},
            ],
            "also_observed": [],
        },
        {
            "id": "f-med",
            "title": "Verbose error pages",
            "category": "Information Disclosure",
            "description": "Stack traces leak framework versions.",
            "baseScore": 5.3,
            "status": "fixed",
            "occurrences": [
                {"dns_name": "pay.stg.example.com", "environment_slug": "stg", "status": "fixed"},
            ],
            "also_observed": [],
        },
    ]
    if kind == "retest_pack":
        findings = [item for item in findings if any(occ["status"] in {"open", "retest"} for occ in item["occurrences"])]
    normalized = [normalize_finding(item) for item in findings]
    normalized = [item for item in normalized if item]
    metrics, severity_counts, occurrence_counts = compute_metrics(normalized, host_count=3)
    kind_key = str(kind or "application").strip().lower()
    if kind_key in {"env", "environment"}:
        package = "owner_delivery"
        scope = "environment"
    elif kind_key == "host":
        package = "host"
        scope = "host"
    elif kind_key == "wave":
        package = "owner_delivery"
        scope = "wave"
    elif kind_key == "wave_archive":
        package = "wave_archive"
        scope = "wave"
    elif kind_key in PACKAGES:
        package = kind_key
        scope = "wave" if kind_key == "wave_archive" else "application"
    else:
        package = "owner_delivery"
        scope = "application"
    watermark = "PRODUCTION" if package in {"owner_delivery", "host"} else "NON-PROD"
    host_context = {
        "scope": "host",
        "package": "host",
        "application": {"id": 12, "name": "Payments Platform", "roe_link": "https://roe.example.com"},
        "record": {
            "name": "payments.example.com",
            "ip_address": "10.20.10.15",
            "source": "Cloud",
            "application_name": "Payments Platform",
            "description": "Customer checkout edge.",
        },
        "pentest": {
            "status": "In Progress",
            "tested_by": "senior.pentester",
            "test_start_date": "2026-02-01",
            "test_end_date": "2026-02-18",
            "service_desk_link": "https://servicedesk.example.com/TKT-1425",
            "notes": "Focus on auth and session.",
            "open_ports": "22, 443, 587",
            "vulnerable": "Yes",
            "vulnerability_fixed": "No",
            "collaborators": "alice",
        },
        "wave": {"id": "", "name": ""},
        "environments": [{"id": 1, "slug": "prod", "is_production": True}],
        "hosts": [{"record_id": 9, "dns": "payments.example.com", "ip": "10.20.10.15", "env": "prod", "ports": [22, 443, 587]}],
        "findings": normalized,
        "metrics": metrics,
        "open_ports": [22, 443, 587],
        "checklist_states": {},
        "severity_counts": severity_counts,
        "occurrence_counts": occurrence_counts,
        "collaborator_usernames": ["alice"],
        "export": {
            "id": "sample",
            "watermark": "",
            "content_hash": "abc123",
            "signature": "def456",
            "generated_at": "",
        },
        "placeholders": {},
        "generated_by": "senior.pentester",
    }
    involved = collect_involved_people(host_context, normalized) or "senior.pentester"
    host_context["pentest"]["tested_by"] = involved
    if scope == "host":
        stamp_generated_clock(host_context, "senior.pentester")
        return host_context

    app_context = dict(host_context)
    app_context.update(
        {
            "scope": scope,
            "package": package,
            "record": {
                "name": "Payments Platform",
                "ip_address": "",
                "source": "",
                "application_name": "Payments Platform",
                "description": "https://roe.example.com",
            },
            "pentest": {
                **host_context["pentest"],
                "open_ports": "",
                "notes": "",
                "service_desk_link": "",
            },
            "wave": {"id": 4, "name": "Q1 production wave"} if scope == "wave" or package == "wave_archive" else {"id": "", "name": ""},
            "environments": [
                {"id": 1, "slug": "prod", "is_production": True},
                {"id": 2, "slug": "stg", "is_production": False},
            ],
            "hosts": [
                {"record_id": 9, "dns": "pay.example.com", "ip": "", "env": "prod", "ports": []},
                {"record_id": 10, "dns": "pay.stg.example.com", "ip": "", "env": "stg", "ports": []},
            ],
            "open_ports": [],
            "export": {
                "id": "sample",
                "watermark": watermark,
                "content_hash": "abc123def",
                "signature": "signedhash",
                "generated_at": "",
            },
        }
    )
    stamp_generated_clock(app_context, "senior.pentester")
    return app_context


__all__ = [
    "BLOCK_TYPES",
    "CHART_IDS",
    "DROP_BLOCK_KEYS",
    "FINDINGS_EXPORT_CAP",
    "PACKAGES",
    "PRINT_INK_DEFAULT",
    "SCOPES",
    "SEVERITY_PRINT_HEX",
    "SEVERITY_CELL_HEX",
    "STATUS_GLYPHS",
    "STATUS_LABELS",
    "TOKEN_REGISTRY",
    "UnknownBlockError",
    "UnknownChartError",
    "UnknownTokenError",
    "coerce_report_context",
    "collect_template_tokens",
    "compute_metrics",
    "context_from_host_record",
    "hash_export_payload",
    "lint_template_tokens",
    "normalize_finding",
    "collect_involved_people",
    "hydrate_finding_fields",
    "split_finding_narrative",
    "strip_leading_title",
    "format_report_date",
    "resolve_placeholders_strict",
    "sample_report_context",
    "severity_by_env_counts",
    "stamp_generated_clock",
    "token_flat_context",
]
