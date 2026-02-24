import json
import re

from app.config import BASE_DIR, DATA_PATH, DB_PATH
from app.domain.catalogs.checklist_catalog import (
    build_checklist_revision,
    get_canonical_checklist_by_key,
    get_canonical_checklists,
)
from app.domain.catalogs.report_template_catalog import (
    build_report_template_revision,
    get_canonical_report_template_by_key,
    get_canonical_report_templates,
)

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
REPORT_LOGO_URL_PATTERN = re.compile(
    r"^(?:https?://[^/\s]+)?/pentest/images/([a-f0-9]{32}\.(?:png|jpg|jpeg|gif|webp))$",
    re.IGNORECASE,
)
PLACEHOLDER_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")

def get_default_service_checklists():
    """Returns a deep-copy-safe list of seeded service checklist templates."""
    return get_canonical_checklists()


def get_default_report_templates():
    """Returns a deep-copy-safe list of seeded report templates."""
    return get_canonical_report_templates()


def safe_json_load(raw_value, default):
    if not raw_value:
        return default
    if isinstance(raw_value, (list, dict)):
        return raw_value
    try:
        return json.loads(raw_value)
    except Exception:
        return default


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_ports(raw_ports):
    values = raw_ports if isinstance(raw_ports, list) else []
    normalized = []
    for value in values:
        try:
            port = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if 1 <= port <= 65535 and port not in normalized:
            normalized.append(port)
    return normalized


def normalize_template_sections(raw_sections):
    if isinstance(raw_sections, dict):
        raw_sections = [{"name": key, "items": value} for key, value in raw_sections.items()]
    if not isinstance(raw_sections, list):
        return None

    sections = []
    for section in raw_sections:
        if not isinstance(section, dict):
            continue
        name = str(section.get("name", "")).strip()
        if not name:
            continue
        raw_items = section.get("items")
        if not isinstance(raw_items, list):
            continue
        items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id", "")).strip()
            test_name = str(item.get("testName", item.get("title", ""))).strip()
            if not item_id or not test_name:
                continue
            items.append(
                {
                    "id": item_id,
                    "testName": test_name,
                    "description": str(item.get("description", "")).strip(),
                    "tools": str(item.get("tools", "")).strip(),
                }
            )
        if items:
            sections.append({"name": name, "items": items})
    return sections if sections else None


def normalize_checklist_template_payload(payload):
    key = str(payload.get("key", "")).strip().lower()
    if not re.match(r"^[a-z0-9][a-z0-9_-]{1,62}$", key):
        return None, "Template key must be 2-63 chars and use only lowercase letters, numbers, '_' or '-'."

    name = str(payload.get("name", "")).strip()
    if not name:
        return None, "Template name is required."

    service = str(payload.get("service", "")).strip().lower()
    if not service:
        return None, "Service name is required."

    source_value = payload.get("source", "")
    source = "" if source_value is None else str(source_value).strip()
    raw_ports = payload.get("auto_ports", [])
    auto_ports = normalize_ports(raw_ports if isinstance(raw_ports, list) else [])
    sections = normalize_template_sections(payload.get("sections"))
    if not sections:
        return None, "At least one section with valid checklist items is required."

    enabled = payload.get("enabled", True)
    enabled_flag = 1 if bool(enabled) else 0

    return {
        "key": key,
        "name": name,
        "service": service,
        "source": source,
        "auto_ports": json.dumps(auto_ports),
        "sections": json.dumps(sections),
        "enabled": enabled_flag,
    }, None


def serialize_checklist_template(row):
    return {
        "id": row["id"],
        "key": row["key"],
        "name": row["name"],
        "service": row["service"],
        "source": row["source"] or "",
        "auto_ports": normalize_ports(safe_json_load(row["auto_ports"], [])),
        "sections": normalize_template_sections(safe_json_load(row["sections"], [])) or [],
        "enabled": bool(row["enabled"]),
        "is_system": bool(row["is_system"]) if "is_system" in row.keys() else False,
        "is_customized": bool(row["is_customized"]) if "is_customized" in row.keys() else False,
        "system_revision": (row["system_revision"] if "system_revision" in row.keys() else None),
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def normalize_report_template_definition(raw_definition):
    if not isinstance(raw_definition, dict):
        return None, "Template definition must be a JSON object."

    blocks = raw_definition.get("blocks")
    if not isinstance(blocks, list) or len(blocks) == 0:
        return None, "Template definition must include a non-empty 'blocks' array."

    normalized_blocks = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type", "")).strip().lower()
        if not block_type:
            continue
        normalized_block = {"type": block_type}
        for key, value in block.items():
            if key == "type":
                continue
            normalized_block[key] = value
        normalized_blocks.append(normalized_block)

    if not normalized_blocks:
        return None, "Template definition must contain at least one valid block object."

    branding = normalize_report_branding(raw_definition.get("branding", {}))
    placeholders = normalize_report_placeholders(raw_definition.get("placeholders", {}))

    normalized = {
        "version": to_int(raw_definition.get("version"), 1),
        "branding": branding,
        "placeholders": placeholders,
        "blocks": normalized_blocks,
    }
    return normalized, None


def normalize_report_branding(raw_branding):
    branding = raw_branding if isinstance(raw_branding, dict) else {}

    raw_company = str(branding.get("company_name", "Security Operations") or "Security Operations")
    company_name = re.sub(r"[\x00-\x1F\x7F]", "", raw_company).strip()[:120]
    if not company_name:
        company_name = "Security Operations"

    primary_color = str(branding.get("primary_color", "#0B5CAD") or "").strip()
    if not HEX_COLOR_PATTERN.fullmatch(primary_color):
        primary_color = "#0B5CAD"

    accent_color = str(branding.get("accent_color", "#1E293B") or "").strip()
    if not HEX_COLOR_PATTERN.fullmatch(accent_color):
        accent_color = "#1E293B"

    raw_logo_url = str(branding.get("logo_url", "") or "").strip()
    logo_match = REPORT_LOGO_URL_PATTERN.fullmatch(raw_logo_url)
    logo_url = f"/pentest/images/{logo_match.group(1).lower()}" if logo_match else ""

    raw_logo_asset_id = branding.get("logo_asset_id")
    logo_asset_id = None
    if raw_logo_asset_id is not None and str(raw_logo_asset_id).strip():
        try:
            parsed_logo_asset_id = int(raw_logo_asset_id)
            if parsed_logo_asset_id > 0:
                logo_asset_id = parsed_logo_asset_id
        except (TypeError, ValueError):
            logo_asset_id = None

    return {
        "company_name": company_name,
        "primary_color": primary_color,
        "accent_color": accent_color,
        "logo_asset_id": logo_asset_id,
        "logo_url": logo_url,
    }


def normalize_report_placeholders(raw_placeholders):
    placeholders = raw_placeholders if isinstance(raw_placeholders, dict) else {}
    normalized = {}
    for key, value in placeholders.items():
        normalized_key = str(key or "").strip()
        if not PLACEHOLDER_KEY_PATTERN.fullmatch(normalized_key):
            continue

        text_value = "" if value is None else str(value)
        text_value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text_value).strip()
        normalized[normalized_key] = text_value[:500]
    return normalized


def normalize_report_template_payload(payload):
    key = str(payload.get("key", "")).strip().lower()
    if not re.match(r"^[a-z0-9][a-z0-9_-]{1,62}$", key):
        return None, "Template key must be 2-63 chars and use only lowercase letters, numbers, '_' or '-'."

    name = str(payload.get("name", "")).strip()
    if not name:
        return None, "Template name is required."

    description = str(payload.get("description", "") or "").strip()
    enabled = 1 if bool(payload.get("enabled", True)) else 0

    normalized_definition, definition_error = normalize_report_template_definition(payload.get("template"))
    if definition_error:
        return None, definition_error

    return {
        "key": key,
        "name": name,
        "description": description,
        "template_json": json.dumps(normalized_definition),
        "enabled": enabled,
    }, None


def serialize_report_template(row):
    definition = safe_json_load(row["template_json"], {})
    return {
        "id": row["id"],
        "key": row["key"],
        "name": row["name"],
        "description": row["description"] or "",
        "template": definition if isinstance(definition, dict) else {},
        "enabled": bool(row["enabled"]),
        "is_system": bool(row["is_system"]) if "is_system" in row.keys() else False,
        "is_customized": bool(row["is_customized"]) if "is_customized" in row.keys() else False,
        "system_revision": (row["system_revision"] if "system_revision" in row.keys() else None),
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "DB_PATH",
    "DATA_PATH",
    "BASE_DIR",
    "build_checklist_revision",
    "build_report_template_revision",
    "get_canonical_checklist_by_key",
    "get_canonical_report_template_by_key",
    "get_default_service_checklists",
    "get_default_report_templates",
    "normalize_checklist_template_payload",
    "normalize_report_template_payload",
    "normalize_ports",
    "normalize_template_sections",
    "safe_json_load",
    "serialize_checklist_template",
    "serialize_report_template",
]
