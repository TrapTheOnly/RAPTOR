import hashlib
import json
import logging

from app.domain.catalogs.report_template_catalog import build_report_template_revision
from app.domain.offsec.shared import get_default_report_templates, get_default_service_checklists
from app.integrations.db.connection import DatabaseCursor

logger = logging.getLogger(__name__)


def seed_service_checklists(cursor: DatabaseCursor) -> None:
    checklist_seed_key = "service_checklists_seeded_v2"
    cursor.execute("SELECT value FROM app_meta WHERE key = ?", (checklist_seed_key,))
    checklist_seeded = cursor.fetchone() is not None
    if checklist_seeded:
        return

    canonical_templates = get_default_service_checklists()
    canonical_by_key = {template["key"]: template for template in canonical_templates}

    cursor.execute("SELECT id, key, is_system, is_customized, system_revision FROM service_checklists")
    existing_rows = cursor.fetchall()
    existing_by_key = {row[1]: row for row in existing_rows}

    for key, template in canonical_by_key.items():
        system_revision = hashlib.sha256(
            json.dumps(template, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        auto_ports = json.dumps(template.get("auto_ports", []))
        sections = json.dumps(template.get("sections", []))
        existing = existing_by_key.get(key)

        if not existing:
            cursor.execute(
                """
                INSERT INTO service_checklists (
                    key, name, service, source, auto_ports, sections, enabled,
                    is_system, is_customized, system_revision,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, 0, ?, 'system', (NOW() + INTERVAL '4 hours'), (NOW() + INTERVAL '4 hours'))
                """,
                (
                    template["key"],
                    template["name"],
                    template["service"],
                    template.get("source", ""),
                    auto_ports,
                    sections,
                    system_revision,
                ),
            )
            continue

        existing_id, _, existing_is_system, existing_is_customized, _ = existing
        if int(existing_is_customized or 0) == 0:
            cursor.execute(
                """
                UPDATE service_checklists
                SET name = ?, service = ?, source = ?, auto_ports = ?, sections = ?, enabled = 1,
                    is_system = 1, is_customized = 0, system_revision = ?,
                    updated_at = (NOW() + INTERVAL '4 hours')
                WHERE id = ?
                """,
                (
                    template["name"],
                    template["service"],
                    template.get("source", ""),
                    auto_ports,
                    sections,
                    system_revision,
                    existing_id,
                ),
            )
        else:
            cursor.execute(
                """
                UPDATE service_checklists
                SET is_system = 1,
                    system_revision = ?,
                    updated_at = (NOW() + INTERVAL '4 hours')
                WHERE id = ?
                """,
                (system_revision, existing_id),
            )

    for existing_id, existing_key, existing_is_system, existing_is_customized, _ in existing_rows:
        if int(existing_is_system or 0) == 1 and existing_key not in canonical_by_key:
            if int(existing_is_customized or 0) == 0:
                cursor.execute(
                    """
                    UPDATE service_checklists
                    SET enabled = 0, updated_at = (NOW() + INTERVAL '4 hours')
                    WHERE id = ?
                    """,
                    (existing_id,),
                )

    cursor.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, (NOW() + INTERVAL '4 hours'))",
        (checklist_seed_key,),
    )


def seed_report_templates(cursor: DatabaseCursor) -> None:
    report_seed_key = "report_templates_seeded_v1"
    cursor.execute("SELECT value FROM app_meta WHERE key = ?", (report_seed_key,))
    report_seeded = cursor.fetchone() is not None
    if report_seeded:
        return

    canonical_templates = get_default_report_templates()
    canonical_by_key = {template["key"]: template for template in canonical_templates}

    cursor.execute("SELECT id, key, is_system, is_customized FROM report_templates")
    existing_rows = cursor.fetchall()
    existing_by_key = {row[1]: row for row in existing_rows}

    for key, template in canonical_by_key.items():
        template_key = str(template.get("key", "")).strip().lower()
        template_name = str(template.get("name", "")).strip()
        template_description = str(template.get("description", "") or "").strip()
        blocks = template.get("blocks")

        if not template_key or not template_name or not isinstance(blocks, list) or len(blocks) == 0:
            logger.warning(f"Skipping invalid canonical report template '{key}'.")
            continue

        template_json = json.dumps(template)
        system_revision = build_report_template_revision(template)
        existing = existing_by_key.get(key)

        if not existing:
            cursor.execute(
                """
                INSERT INTO report_templates (
                    key, name, description, template_json, enabled,
                    is_system, is_customized, system_revision,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, 1, 0, ?, 'system', (NOW() + INTERVAL '4 hours'), (NOW() + INTERVAL '4 hours'))
                """,
                (
                    template_key,
                    template_name,
                    template_description,
                    template_json,
                    system_revision,
                ),
            )
            continue

        existing_id, _, existing_is_system, existing_is_customized = existing
        if int(existing_is_customized or 0) == 0:
            cursor.execute(
                """
                UPDATE report_templates
                SET name = ?, description = ?, template_json = ?, enabled = 1,
                    is_system = 1, is_customized = 0, system_revision = ?,
                    updated_at = (NOW() + INTERVAL '4 hours')
                WHERE id = ?
                """,
                (
                    template_name,
                    template_description,
                    template_json,
                    system_revision,
                    existing_id,
                ),
            )
        else:
            cursor.execute(
                """
                UPDATE report_templates
                SET is_system = 1,
                    system_revision = ?,
                    updated_at = (NOW() + INTERVAL '4 hours')
                WHERE id = ?
                """,
                (system_revision, existing_id),
            )

    for existing_id, existing_key, existing_is_system, existing_is_customized in existing_rows:
        if int(existing_is_system or 0) == 1 and existing_key not in canonical_by_key:
            if int(existing_is_customized or 0) == 0:
                cursor.execute(
                    """
                    UPDATE report_templates
                    SET enabled = 0, updated_at = (NOW() + INTERVAL '4 hours')
                    WHERE id = ?
                    """,
                    (existing_id,),
                )

    cursor.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, (NOW() + INTERVAL '4 hours'))",
        (report_seed_key,),
    )


def create_vuln_categories_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vuln_categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_by TEXT,
            created_at TEXT NOT NULL,
            is_custom INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def seed_default_vuln_categories(cursor: DatabaseCursor) -> None:
    cursor.execute("SELECT COUNT(*) FROM vuln_categories")
    if cursor.fetchone()[0] != 0:
        return

    default_categories = [
        "SQL Injection",
        "Blind SQL Injection",
        "Stored XSS",
        "Reflected XSS",
        "DOM-based XSS",
        "Cross-Site Request Forgery (CSRF)",
        "Server-Side Request Forgery (SSRF)",
        "Remote Code Execution (RCE)",
        "Command Injection",
        "OS Command Injection",
        "Local File Inclusion (LFI)",
        "Remote File Inclusion (RFI)",
        "Path Traversal",
        "Directory Listing",
        "Insecure File Upload",
        "XML External Entity (XXE)",
        "XPath Injection",
        "LDAP Injection",
        "Server-Side Template Injection (SSTI)",
        "Insecure Deserialization",
        "Broken Authentication",
        "Weak Password Policy",
        "Credential Stuffing",
        "Session Fixation",
        "Session Hijacking",
        "Broken Access Control",
        "IDOR",
        "Privilege Escalation",
        "Open Redirect",
        "Clickjacking",
        "CORS Misconfiguration",
        "HTTP Request Smuggling",
        "HTTP Response Splitting",
        "Host Header Injection",
        "Prototype Pollution",
        "Business Logic Flaw",
        "Information Disclosure",
        "Sensitive Data Exposure",
        "Insufficient Logging & Monitoring",
        "Security Misconfiguration",
        "Insecure Defaults",
        "Rate Limiting Missing",
        "Brute Force",
        "JWT Weakness",
        "OAuth Misconfiguration",
        "SAML Misconfiguration",
        "API Mass Assignment",
        "API Rate Limit Bypass",
        "Insecure Direct Object Reference (IDOR)",
        "Cache Poisoning",
        "CRLF Injection",
        "HTTP Verb Tampering",
    ]
    for name in default_categories:
        cursor.execute(
            """
            INSERT INTO vuln_categories (name, created_by, created_at, is_custom)
            VALUES (?, ?, (NOW() + INTERVAL '4 hours'), 0)
            """,
            (name, "system"),
        )
