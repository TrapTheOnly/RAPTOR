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
    safe_text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", safe_text)
    safe_text = MARKDOWN_LINK_PATTERN.sub(
        lambda match: (
            f"<a href='{safe_url}'>{match.group(1)}</a>"
            if (safe_url := _sanitize_link_target(match.group(2)))
            else match.group(1)
        ),
        safe_text,
    )
    safe_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe_text)
    safe_text = re.sub(r"__(.+?)__", r"<b>\1</b>", safe_text)
    safe_text = re.sub(r"~~(.+?)~~", r"<strike>\1</strike>", safe_text)
    safe_text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", safe_text)
    safe_text = re.sub(
        r"(?<![A-Za-z0-9_])_(?!_)(.+?)(?<!_)_(?![A-Za-z0-9_])",
        r"<i>\1</i>",
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
    from app.integrations.reporting.report_context import coerce_report_context, token_flat_context

    context_payload = coerce_report_context(record_data or {}, generated_by=generated_by)
    findings = [item for item in (context_payload.get("findings") or []) if isinstance(item, dict)]
    open_ports = context_payload.get("open_ports") or []
    if not isinstance(open_ports, list):
        open_ports = parse_open_ports(open_ports)

    checklist_states = context_payload.get("checklist_states") or {}
    if not isinstance(checklist_states, dict):
        checklist_states = {}
    selected_checklists = checklist_states.get("selected", []) if isinstance(checklist_states, dict) else []
    if not isinstance(selected_checklists, list):
        selected_checklists = []
    checklist_statuses = checklist_states.get("statuses", {}) if isinstance(checklist_states, dict) else {}
    if not isinstance(checklist_statuses, dict):
        checklist_statuses = {}

    def get_template_status_map(template_key, item_ids):
        nested_statuses = checklist_statuses.get(template_key, {})
        if not isinstance(nested_statuses, dict):
            nested_statuses = {}
        status_map = {}
        for item_id in item_ids:
            nested_value = nested_statuses.get(item_id)
            flat_value = checklist_statuses.get(item_id)
            value = nested_value if nested_value is not None else flat_value
            if isinstance(value, str):
                status_map[item_id] = value
        return status_map

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

        status_map = get_template_status_map(key, item_ids)
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

    metrics = dict(context_payload.get("metrics") or {})
    metrics["checklist_total"] = checklist_total
    metrics["checklist_completed"] = checklist_completed
    metrics["checklist_irrelevant"] = checklist_irrelevant
    metrics["checklist_unstarted"] = checklist_unstarted
    metrics["checklist_percentage"] = (
        round((checklist_completed / checklist_total) * 100, 1) if checklist_total else 0
    )
    metrics["open_ports_count"] = len(open_ports)
    context_payload["metrics"] = metrics

    collaborator_usernames = list(context_payload.get("collaborator_usernames") or [])
    context = {
        "generated_at": context_payload.get("generated_at", ""),
        "generated_date": context_payload.get("generated_date", ""),
        "generated_by": context_payload.get("generated_by", ""),
        "scope": context_payload.get("scope", ""),
        "package": context_payload.get("package", ""),
        "application": context_payload.get("application") or {},
        "record": context_payload.get("record") or {},
        "pentest": context_payload.get("pentest") or {},
        "wave": context_payload.get("wave") or {},
        "metrics": metrics,
        "export": context_payload.get("export") or {},
        "placeholders": context_payload.get("placeholders") or {},
    }
    flat_context = token_flat_context(context)

    severity_counts = context_payload.get("severity_counts") or {
        "Critical": metrics.get("critical_count", 0),
        "High": metrics.get("high_count", 0),
        "Medium": metrics.get("medium_count", 0),
        "Low": metrics.get("low_count", 0),
        "Informational": metrics.get("informational_count", 0),
    }
    occurrence_counts = context_payload.get("occurrence_counts") or {
        "open": metrics.get("occurrence_open", 0),
        "draft": metrics.get("occurrence_draft", 0),
        "retest": metrics.get("occurrence_retest", 0),
        "fixed": metrics.get("occurrence_fixed", 0),
        "accepted": metrics.get("occurrence_accepted", 0),
        "not_affected": metrics.get("occurrence_not_affected", 0),
    }

    return {
        "context": context,
        "report_context": context_payload,
        "flat_context": flat_context,
        "open_ports": open_ports,
        "vulnerabilities": findings,
        "findings": findings,
        "severity_counts": severity_counts,
        "occurrence_counts": occurrence_counts,
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
