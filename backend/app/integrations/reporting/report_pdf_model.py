import datetime
import html
import json
import re
from urllib.parse import urlparse

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
IMAGE_REFERENCE_PATTERN = re.compile(
    r"^(?:https?://[^/\s]+)?/pentest/images/([a-f0-9]{32}\.(?:png|jpg|jpeg|gif|webp))$",
    re.IGNORECASE,
)
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
ALLOWED_LINK_SCHEMES = {"http", "https", "mailto"}


def safe_json_load(raw_value, default):
    if raw_value is None:
        return default
    if isinstance(raw_value, (list, dict)):
        return raw_value
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            return json.loads(raw_value)
        except Exception:
            return default
    return default


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_open_ports(raw_ports):
    if isinstance(raw_ports, list):
        values = raw_ports
    else:
        values = str(raw_ports or "").replace(";", ",").split(",")
    normalized = []
    for value in values:
        port = to_int(str(value).strip(), default=None)
        if port is None:
            continue
        if 1 <= port <= 65535 and port not in normalized:
            normalized.append(port)
    return sorted(normalized)


def severity_from_score(score):
    value = to_float(score, 0.0)
    if value >= 9.0:
        return "Critical"
    if value >= 7.0:
        return "High"
    if value >= 4.0:
        return "Medium"
    if value > 0.0:
        return "Low"
    return "Informational"


def flatten(prefix, value, target):
    if isinstance(value, dict):
        for key, inner in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flatten(path, inner, target)
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            flatten(path, inner, target)
    else:
        target[prefix] = "" if value is None else str(value)


def resolve_placeholders(value, flat_context):
    if not isinstance(value, str):
        return value

    def repl(match):
        key = match.group(1).strip()
        return flat_context.get(key, "")

    return PLACEHOLDER_PATTERN.sub(repl, value)


def _sanitize_link_target(raw_url):
    candidate = html.unescape(str(raw_url or "")).strip()
    if not candidate or len(candidate) > 500:
        return None
    if re.search(r"[\x00-\x1F\x7F]", candidate):
        return None
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in ALLOWED_LINK_SCHEMES:
        return None
    return html.escape(candidate, quote=True)


def replace_inline_markdown(text):
    safe_text = html.escape(str(text or ""))
    safe_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe_text)
    safe_text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", safe_text)
    safe_text = MARKDOWN_LINK_PATTERN.sub(
        lambda match: (
            f"<a href='{safe_url}'>{match.group(1)}</a>"
            if (safe_url := _sanitize_link_target(match.group(2)))
            else match.group(1)
        ),
        safe_text,
    )
    return safe_text


def build_service_name(port):
    service_map = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        110: "POP3",
        123: "NTP",
        143: "IMAP",
        161: "SNMP",
        389: "LDAP",
        443: "HTTPS",
        445: "SMB",
        465: "SMTPS",
        587: "SMTP Submission",
        636: "LDAPS",
        1433: "MSSQL",
        1521: "Oracle",
        2049: "NFS",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        6379: "Redis",
        8080: "HTTP Alternate",
        8443: "HTTPS Alternate",
    }
    return service_map.get(port, "Unknown")


def build_report_model(record_data, checklist_templates, generated_by=None):
    vulnerabilities = safe_json_load(record_data.get("vulnerabilities"), [])
    if not isinstance(vulnerabilities, list):
        vulnerabilities = []
    vulnerabilities = [item for item in vulnerabilities if isinstance(item, dict)]

    open_ports = parse_open_ports(record_data.get("open_ports"))
    checklist_states = safe_json_load(record_data.get("checklist_states"), {})
    selected_checklists = checklist_states.get("selected", []) if isinstance(checklist_states, dict) else []
    if not isinstance(selected_checklists, list):
        selected_checklists = []
    checklist_statuses = checklist_states.get("statuses", {}) if isinstance(checklist_states, dict) else {}
    if not isinstance(checklist_statuses, dict):
        checklist_statuses = {}

    templates = []
    for template in checklist_templates or []:
        if not isinstance(template, dict):
            continue
        if template.get("enabled") is False:
            continue
        key = str(template.get("key", "")).strip()
        sections = template.get("sections")
        if not key or not isinstance(sections, list):
            continue
        templates.append(template)

    open_port_set = set(open_ports)
    enabled_template_keys = set([str(value).strip() for value in selected_checklists if str(value).strip()])
    for template in templates:
        for port in template.get("auto_ports", []):
            if to_int(port, -1) in open_port_set:
                enabled_template_keys.add(template.get("key"))
                break

    checklist_progress_rows = []
    checklist_completed = 0
    checklist_irrelevant = 0
    checklist_unstarted = 0
    checklist_total = 0

    for template in templates:
        key = template.get("key")
        if key not in enabled_template_keys:
            continue
        item_ids = []
        for section in template.get("sections", []):
            for item in section.get("items", []):
                item_id = str(item.get("id", "")).strip()
                if item_id:
                    item_ids.append(item_id)
        if not item_ids:
            continue

        status_map = checklist_statuses.get(key, {})
        if not isinstance(status_map, dict):
            status_map = {}
        completed = 0
        irrelevant = 0
        for item_id in item_ids:
            status = str(status_map.get(item_id, "unstarted")).strip().lower()
            if status == "completed":
                completed += 1
            elif status == "irrelevant":
                irrelevant += 1

        total = len(item_ids)
        unstarted = max(total - completed - irrelevant, 0)
        checklist_progress_rows.append(
            {
                "name": template.get("name", key),
                "service": template.get("service", ""),
                "completed": completed,
                "irrelevant": irrelevant,
                "unstarted": unstarted,
                "total": total,
                "percentage": round((completed / total) * 100, 1) if total else 0,
            }
        )

        checklist_total += total
        checklist_completed += completed
        checklist_irrelevant += irrelevant
        checklist_unstarted += unstarted

    severity_counts = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
        "Informational": 0,
    }
    for vuln in vulnerabilities:
        severity = severity_from_score(vuln.get("baseScore"))
        severity_counts[severity] += 1

    vulnerability_count = len(vulnerabilities)
    vulnerability_fixed = to_int(record_data.get("vulnerability_fixed"), 0) == 1
    fixed_findings = vulnerability_count if vulnerability_fixed else 0
    open_findings = max(vulnerability_count - fixed_findings, 0)

    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    raw_collaborators = record_data.get("collaborators") or []
    if isinstance(raw_collaborators, list):
        collaborator_usernames = [str(c).strip() for c in raw_collaborators if str(c).strip()]
    else:
        collaborator_usernames = []

    assignee = record_data.get("tested_by") or "Unassigned"
    resolved_generated_by = generated_by or assignee

    context = {
        "generated_at": generated_at,
        "generated_date": generated_at.split(" ")[0],
        "generated_by": resolved_generated_by,
        "record": {
            "name": record_data.get("name", ""),
            "ip_address": record_data.get("ip_address", ""),
            "source": record_data.get("source", ""),
            "application_name": record_data.get("application_name", ""),
            "description": record_data.get("description", ""),
        },
        "pentest": {
            "status": record_data.get("status", "Not Started"),
            "tested_by": assignee,
            "test_start_date": record_data.get("test_start_date", ""),
            "test_end_date": record_data.get("test_end_date", ""),
            "service_desk_link": record_data.get("service_desk_link", ""),
            "notes": record_data.get("notes", ""),
            "open_ports": ", ".join([str(port) for port in open_ports]),
            "vulnerable": "Yes" if to_int(record_data.get("vulnerable"), 0) == 1 else "No",
            "vulnerability_fixed": "Yes" if vulnerability_fixed else "No",
            "collaborators": ", ".join(collaborator_usernames) if collaborator_usernames else "",
        },
        "metrics": {
            "vulnerability_count": vulnerability_count,
            "critical_count": severity_counts["Critical"],
            "high_count": severity_counts["High"],
            "medium_count": severity_counts["Medium"],
            "low_count": severity_counts["Low"],
            "informational_count": severity_counts["Informational"],
            "critical_high_count": severity_counts["Critical"] + severity_counts["High"],
            "open_findings": open_findings,
            "fixed_findings": fixed_findings,
            "open_ports_count": len(open_ports),
            "checklist_total": checklist_total,
            "checklist_completed": checklist_completed,
            "checklist_irrelevant": checklist_irrelevant,
            "checklist_unstarted": checklist_unstarted,
            "checklist_percentage": round((checklist_completed / checklist_total) * 100, 1)
            if checklist_total
            else 0,
        },
    }

    flat_context = {}
    flatten("", context, flat_context)

    return {
        "context": context,
        "flat_context": flat_context,
        "open_ports": open_ports,
        "vulnerabilities": vulnerabilities,
        "severity_counts": severity_counts,
        "checklist_progress_rows": checklist_progress_rows,
        "collaborator_usernames": collaborator_usernames,
    }


__all__ = [
    "IMAGE_REFERENCE_PATTERN",
    "MARKDOWN_IMAGE_PATTERN",
    "build_report_model",
    "build_service_name",
    "flatten",
    "replace_inline_markdown",
    "resolve_placeholders",
    "safe_json_load",
    "severity_from_score",
    "to_float",
    "to_int",
]
