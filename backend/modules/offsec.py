import os
import uuid
import re
import ftplib
import sqlite3
import logging
import json
from io import BytesIO
import xml.etree.ElementTree as ET
from modules.user import login_required_json
from modules.admin import admin_required
from modules.permissions import permission_required, user_has_permission
from modules.checklist_catalog import (
    build_checklist_revision,
    get_canonical_checklist_by_key,
    get_canonical_checklists,
)
from modules.report_template_catalog import (
    build_report_template_revision,
    get_canonical_report_template_by_key,
    get_canonical_report_templates,
)
from modules.report_pdf import render_pentest_report_pdf
from flask import jsonify, request, send_file, session, current_app

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_PATH, "database.db")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
IMAGE_DIR = "images"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
IMAGE_FILENAME_PATTERN = r"[a-f0-9]{32}\.(?:png|jpg|jpeg|gif|webp)"
IMAGE_REFERENCE_PATTERN = re.compile(
    rf"(?:https?://[^)\s]+)?/pentest/images/({IMAGE_FILENAME_PATTERN})",
    re.IGNORECASE
)

def get_default_service_checklists():
    """Returns a deep-copy-safe list of seeded service checklist templates."""
    return get_canonical_checklists()


def _safe_json_load(raw_value, default):
    if not raw_value:
        return default
    if isinstance(raw_value, (list, dict)):
        return raw_value
    try:
        return json.loads(raw_value)
    except Exception:
        return default


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_ports(raw_ports):
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


def _normalize_template_sections(raw_sections):
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
            items.append({
                "id": item_id,
                "testName": test_name,
                "description": str(item.get("description", "")).strip(),
                "tools": str(item.get("tools", "")).strip()
            })
        if items:
            sections.append({"name": name, "items": items})
    return sections if sections else None


def _normalize_checklist_template_payload(payload):
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
    auto_ports = _normalize_ports(raw_ports if isinstance(raw_ports, list) else [])
    sections = _normalize_template_sections(payload.get("sections"))
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
        "enabled": enabled_flag
    }, None


def _serialize_checklist_template(row):
    return {
        "id": row["id"],
        "key": row["key"],
        "name": row["name"],
        "service": row["service"],
        "source": row["source"] or "",
        "auto_ports": _normalize_ports(_safe_json_load(row["auto_ports"], [])),
        "sections": _normalize_template_sections(_safe_json_load(row["sections"], [])) or [],
        "enabled": bool(row["enabled"]),
        "is_system": bool(row["is_system"]) if "is_system" in row.keys() else False,
        "is_customized": bool(row["is_customized"]) if "is_customized" in row.keys() else False,
        "system_revision": (row["system_revision"] if "system_revision" in row.keys() else None),
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }


def get_default_report_templates():
    """Returns a deep-copy-safe list of seeded report templates."""
    return get_canonical_report_templates()


def _normalize_report_template_definition(raw_definition):
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

    branding = raw_definition.get("branding", {})
    placeholders = raw_definition.get("placeholders", {})

    normalized = {
        "version": _to_int(raw_definition.get("version"), 1),
        "branding": branding if isinstance(branding, dict) else {},
        "placeholders": placeholders if isinstance(placeholders, dict) else {},
        "blocks": normalized_blocks
    }
    return normalized, None


def _normalize_report_template_payload(payload):
    key = str(payload.get("key", "")).strip().lower()
    if not re.match(r"^[a-z0-9][a-z0-9_-]{1,62}$", key):
        return None, "Template key must be 2-63 chars and use only lowercase letters, numbers, '_' or '-'."

    name = str(payload.get("name", "")).strip()
    if not name:
        return None, "Template name is required."

    description = str(payload.get("description", "") or "").strip()
    enabled = 1 if bool(payload.get("enabled", True)) else 0

    normalized_definition, definition_error = _normalize_report_template_definition(
        payload.get("template")
    )
    if definition_error:
        return None, definition_error

    return {
        "key": key,
        "name": name,
        "description": description,
        "template_json": json.dumps(normalized_definition),
        "enabled": enabled
    }, None


def _serialize_report_template(row):
    definition = _safe_json_load(row["template_json"], {})
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
        "updated_at": row["updated_at"]
    }


def _guess_image_mimetype(extension):
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp"
    }.get(extension, "application/octet-stream")

def ftp_connect():
    """Connects to the FTP server and returns the FTP object."""
    try:
        ftp = ftplib.FTP(FTP_HOST)
        ftp.login(user=FTP_USER, passwd=FTP_PASS)
        return ftp
    except Exception as e:
        logger.error(f"FTP connection error: {e}")
        raise

def ensure_ftp_dir(ftp, dirname):
    try:
        ftp.cwd(dirname)
        ftp.cwd("..")
    except Exception:
        try:
            ftp.mkd(dirname)
        except Exception:
            pass

def save_image(file_data, extension):
    """Saves an image to the FTP server and returns its filename."""
    ftp = ftp_connect()
    ensure_ftp_dir(ftp, IMAGE_DIR)
    unique_filename = f"{uuid.uuid4().hex}.{extension}"
    file_stream = BytesIO(file_data)
    file_stream.seek(0)
    ftp.storbinary(f"STOR {IMAGE_DIR}/{unique_filename}", file_stream)
    ftp.quit()
    return unique_filename

def fetch_image(filename):
    """Fetches an image from the FTP server."""
    ftp = ftp_connect()
    file_data = BytesIO()
    ftp.retrbinary(f"RETR {IMAGE_DIR}/{filename}", file_data.write)
    ftp.quit()
    file_data.seek(0)
    return file_data

def delete_image(filename):
    """Deletes an uploaded pentest image from FTP storage."""
    ftp = ftp_connect()
    ftp.delete(f"{IMAGE_DIR}/{filename}")
    ftp.quit()

def _extract_image_filenames(raw_value):
    text = str(raw_value or "")
    return {match.lower() for match in IMAGE_REFERENCE_PATTERN.findall(text)}

def _extract_image_filenames_from_vulnerabilities(raw_value):
    filenames = set()
    parsed = []

    if isinstance(raw_value, list):
        parsed = raw_value
    elif isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
        except Exception:
            parsed = []

    if not isinstance(parsed, list):
        return filenames

    for vulnerability in parsed:
        if not isinstance(vulnerability, dict):
            continue
        filenames.update(_extract_image_filenames(vulnerability.get("description", "")))
    return filenames

def _collect_referenced_image_filenames(description, notes, vulnerabilities):
    filenames = set()
    filenames.update(_extract_image_filenames(description))
    filenames.update(_extract_image_filenames(notes))
    filenames.update(_extract_image_filenames_from_vulnerabilities(vulnerabilities))
    return filenames

def _is_image_referenced_anywhere(filename):
    like_value = f"%{filename}%"
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT 1 FROM records WHERE description LIKE ? LIMIT 1", (like_value,))
        if c.fetchone():
            return True

        c.execute("""
            SELECT 1
            FROM pentest_data
            WHERE notes LIKE ? OR vulnerabilities LIKE ?
            LIMIT 1
        """, (like_value, like_value))
        return c.fetchone() is not None

def _cleanup_unreferenced_images(filenames):
    for filename in sorted(set(filenames)):
        if _is_image_referenced_anywhere(filename):
            continue
        try:
            delete_image(filename)
            logger.info(f"Deleted unreferenced image from FTP: {filename}")
        except Exception as e:
            logger.warning(f"Failed to delete unreferenced image '{filename}': {e}")

def _can_user_access_image(filename):
    username = session.get('username')
    role = session.get('user_type')
    if user_has_permission(username, role, 'modify_others_pentests_admin'):
        return True
    if not username:
        return False

    like_value = f"%{filename}%"
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT 1
            FROM pentest_data
            WHERE tested_by = ?
              AND (notes LIKE ? OR vulnerabilities LIKE ?)
            LIMIT 1
        """, (username, like_value, like_value))
        if c.fetchone():
            return True

        c.execute("""
            SELECT 1
            FROM records r
            JOIN pentest_data p ON p.record_id = r.id
            WHERE p.tested_by = ?
              AND r.description LIKE ?
            LIMIT 1
        """, (username, like_value))
        return c.fetchone() is not None

def save_report(record_id, file_data):
    """Saves a report file to the FTP server."""
    try:
        ftp = ftp_connect()
        unique_filename = f"{record_id}_{uuid.uuid4()}.pdf"
        file_stream = BytesIO(file_data)
        file_stream.seek(0)

        ftp.storbinary(f'STOR {unique_filename}', file_stream)
        ftp.quit()
        return unique_filename
    except Exception as e:
        logger.error(f"Error saving report for record {record_id}: {e}")
        raise

def delete_report(relative_path):
    """Deletes a report file from the FTP server."""
    try:
        ftp = ftp_connect()
        ftp.delete(relative_path)
        ftp.quit()
        logger.info(f"Deleted report file: {relative_path}")
    except Exception as e:
        logger.error(f"Error deleting report file {relative_path}: {e}")
        raise

def get_pentest_data_internal(record_id=None):
    """Internal function to fetch pentest data (all records or a single record)."""
    default_pentest = {
        'report_file': None,
        'generated_report_file': None,
        'generated_report_template_id': None,
        'generated_report_generated_at': None,
        'vulnerable': 0,
        'tested_by': None,
        'test_start_date': None,
        'test_end_date': None,
        'vulnerability_fixed': 0,
        'service_desk_link': None,
        'status': 'Not Started',
        'open_ports': "",
        'notes': "",
        'owasp_checklist': "",
        'checklist_states': "",
        'vulnerabilities': ""
    }
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            if record_id is not None:
                c.execute("""
                    SELECT
                        r.id,
                        r.name,
                        r.ip_address,
                        r.source,
                        r.status,
                        r.creation_date,
                        r.last_modification_date,
                        r.application_owner,
                        r.maintainer,
                        r.description,
                        r.application_id,
                        a.name AS application_name
                    FROM records r
                    LEFT JOIN applications a ON r.application_id = a.id
                    WHERE r.id = ?
                """, (record_id,))
                record_row = c.fetchone()
                if not record_row:
                    return None
                record = dict(record_row)

                c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
                pentest_row = c.fetchone()
                pentest = dict(pentest_row) if pentest_row else default_pentest

                return {
                    **pentest,
                    'recordId': record['id'],
                    'name': record['name'],
                    'ip_address': record['ip_address'],
                    'source': record['source'],
                    'description': record.get('description', ''),
                    'application_id': record.get('application_id'),
                    'application_name': record.get('application_name')
                }

            c.execute("""
                SELECT
                    r.id,
                    r.name,
                    r.ip_address,
                    r.source,
                    r.status,
                    r.creation_date,
                    r.last_modification_date,
                    r.application_owner,
                    r.maintainer,
                    r.description,
                    r.application_id,
                    a.name AS application_name
                FROM records r
                LEFT JOIN applications a ON r.application_id = a.id
            """)
            rows = c.fetchall()
            dns_records = [dict(ix) for ix in rows]

            c.execute("SELECT * FROM pentest_data")
            pentest_records = {row['record_id']: dict(row) for row in c.fetchall()}

            return [
                {
                    **pentest_records.get(record['id'], default_pentest),
                    'recordId': record['id'],
                    'name': record['name'],
                    'ip_address': record['ip_address'],
                    'source': record['source'],
                    'description': record.get('description', ''),
                    'application_id': record.get('application_id'),
                    'application_name': record.get('application_name')
                } for record in dns_records
            ]

    except Exception as e:
        logger.error(f"Error fetching record details: {e}")
        return None

def get_record_details_internal(record_id):
    """Internal function to fetch record details."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM records WHERE id = ?", (record_id,))
            return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching record details for ID {record_id}: {e}")
        return None

def get_pentest_users_internal():
    """Fetches users with the 'pentest' role from the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            users = c.execute(
                "SELECT id, username FROM allowed_users WHERE role IN ('pentester', 'manager')"
            ).fetchall()
            return [{"id": user['id'], "username": user['username']} for user in users]
    except Exception as e:
        logger.error(f"Error fetching pentesters: {e}")
        return None

@permission_required('reassign_pentests_admin')
def get_pentest_users():
    """GET /pentest_users: Get users with pentest role."""
    try:
        users = get_pentest_users_internal()
        return jsonify(users), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching pentest users: {e}")
        return jsonify({"message": "Error fetching pentest users"}), 500

def get_pentest_row(record_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
            return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching pentest data for ID {record_id}: {e}")
        return None

def enforce_pentest_record_access(record_id, action_verb="access"):
    """
    Enforce record-level access for pentest resources.
    - Admin/manager users with 'modify_others_pentests_admin' can access any record.
    - Others can access only records assigned to their username.
    - Unassigned records are blocked for non-privileged users.
    """
    username = session.get('username')
    role = session.get('user_type')
    can_modify_others = user_has_permission(username, role, 'modify_others_pentests_admin')
    if can_modify_others:
        return True, None

    pentest_row = get_pentest_row(record_id)
    assigned_user = (pentest_row['tested_by'] if pentest_row and pentest_row['tested_by'] else '').strip()
    if not assigned_user:
        return False, f"Unassigned pentest records must be assigned before {action_verb}."
    if assigned_user != (username or '').strip():
        return False, f"You are not allowed to {action_verb} another user's pentest."
    return True, None


@permission_required('view_pentest_page')
def get_checklist_templates():
    """GET /checklist-templates: List checklist templates."""
    try:
        include_disabled_requested = str(request.args.get('include_disabled', '')).lower() in {"1", "true", "yes"}
        include_disabled = include_disabled_requested and session.get("user_type") == "admin"

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            query = """
                SELECT id, key, name, service, source, auto_ports, sections, enabled,
                       is_system, is_customized, system_revision,
                       created_by, created_at, updated_at
                FROM service_checklists
            """
            if not include_disabled:
                query += " WHERE enabled = 1"
            query += " ORDER BY name COLLATE NOCASE ASC"
            c.execute(query)
            rows = c.fetchall()
        templates = [_serialize_checklist_template(row) for row in rows]
        return jsonify({"templates": templates}), 200
    except Exception as e:
        logger.error(f"Error fetching checklist templates: {e}")
        return jsonify({"error": "Failed to fetch checklist templates."}), 500


@admin_required
def create_checklist_template():
    """POST /checklist-templates: Create a checklist template."""
    payload = request.get_json(silent=True) or {}
    normalized, validation_error = _normalize_checklist_template_payload(payload)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    created_by = session.get("username", "admin")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO service_checklists (
                    key, name, service, source, auto_ports, sections, enabled,
                    is_system, is_customized, system_revision,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, ?, datetime('now', '+4 hours'), datetime('now', '+4 hours'))
            """, (
                normalized["key"],
                normalized["name"],
                normalized["service"],
                normalized["source"],
                normalized["auto_ports"],
                normalized["sections"],
                normalized["enabled"],
                created_by
            ))
            template_id = c.lastrowid
            conn.commit()
        return jsonify({"message": "Checklist template created.", "id": template_id}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "Template key already exists."}), 400
    except Exception as e:
        logger.error(f"Error creating checklist template: {e}")
        return jsonify({"error": "Failed to create checklist template."}), 500


@admin_required
def update_checklist_template(template_id):
    """PUT /checklist-templates/<id>: Update a checklist template."""
    payload = request.get_json(silent=True) or {}

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT id, key, name, service, source, auto_ports, sections, enabled,
                       is_system, is_customized, system_revision
                FROM service_checklists
                WHERE id = ?
            """, (template_id,))
            existing = c.fetchone()
            if not existing:
                return jsonify({"error": "Template not found."}), 404

            if payload.get("key") and bool(existing["is_system"]):
                requested_key = str(payload.get("key", "")).strip().lower()
                if requested_key and requested_key != existing["key"]:
                    return jsonify({"error": "System template key cannot be changed."}), 400

            merged_payload = {
                "key": payload.get("key", existing["key"]),
                "name": payload.get("name", existing["name"]),
                "service": payload.get("service", existing["service"]),
                "source": payload.get("source", existing["source"]),
                "auto_ports": payload.get("auto_ports", _safe_json_load(existing["auto_ports"], [])),
                "sections": payload.get("sections", _safe_json_load(existing["sections"], [])),
                "enabled": payload.get("enabled", bool(existing["enabled"]))
            }

            normalized, validation_error = _normalize_checklist_template_payload(merged_payload)
            if validation_error:
                return jsonify({"error": validation_error}), 400

            mark_customized = 1 if bool(existing["is_system"]) else int(bool(existing["is_customized"]))
            c.execute("""
                UPDATE service_checklists
                SET key = ?, name = ?, service = ?, source = ?, auto_ports = ?, sections = ?, enabled = ?,
                    is_customized = ?,
                    updated_at = datetime('now', '+4 hours')
                WHERE id = ?
            """, (
                normalized["key"],
                normalized["name"],
                normalized["service"],
                normalized["source"],
                normalized["auto_ports"],
                normalized["sections"],
                normalized["enabled"],
                mark_customized,
                template_id
            ))
            conn.commit()
        return jsonify({"message": "Checklist template updated."}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "Template key already exists."}), 400
    except Exception as e:
        logger.error(f"Error updating checklist template {template_id}: {e}")
        return jsonify({"error": "Failed to update checklist template."}), 500


@admin_required
def delete_checklist_template(template_id):
    """DELETE /checklist-templates/<id>: Delete a checklist template."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT is_system FROM service_checklists WHERE id = ?", (template_id,))
            existing = c.fetchone()
            if not existing:
                return jsonify({"error": "Template not found."}), 404
            if bool(existing["is_system"]):
                return jsonify({"error": "System templates cannot be deleted. Disable or reset them instead."}), 400

            c.execute("DELETE FROM service_checklists WHERE id = ?", (template_id,))
            conn.commit()
        return jsonify({"message": "Checklist template deleted."}), 200
    except Exception as e:
        logger.error(f"Error deleting checklist template {template_id}: {e}")
        return jsonify({"error": "Failed to delete checklist template."}), 500


@admin_required
def reset_checklist_template_to_canonical(template_id):
    """POST /checklist-templates/<id>/reset: Reset system template to canonical definition."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT id, key, is_system
                FROM service_checklists
                WHERE id = ?
            """, (template_id,))
            existing = c.fetchone()
            if not existing:
                return jsonify({"error": "Template not found."}), 404
            if not bool(existing["is_system"]):
                return jsonify({"error": "Only system templates can be reset to canonical."}), 400

            canonical = get_canonical_checklist_by_key(existing["key"])
            if not canonical:
                return jsonify({"error": "Canonical template definition not found for this key."}), 404

            normalized, validation_error = _normalize_checklist_template_payload(canonical)
            if validation_error:
                return jsonify({"error": f"Canonical template is invalid: {validation_error}"}), 500

            system_revision = build_checklist_revision(canonical)
            c.execute("""
                UPDATE service_checklists
                SET name = ?, service = ?, source = ?, auto_ports = ?, sections = ?, enabled = 1,
                    is_customized = 0, system_revision = ?,
                    updated_at = datetime('now', '+4 hours')
                WHERE id = ?
            """, (
                normalized["name"],
                normalized["service"],
                normalized["source"],
                normalized["auto_ports"],
                normalized["sections"],
                system_revision,
                template_id
            ))
            conn.commit()
        return jsonify({"message": "Checklist template reset to canonical successfully."}), 200
    except Exception as e:
        logger.error(f"Error resetting checklist template {template_id} to canonical: {e}")
        return jsonify({"error": "Failed to reset checklist template."}), 500


@permission_required('view_pentest_page')
def get_report_templates():
    """GET /report-templates: List report templates."""
    try:
        include_disabled_requested = str(request.args.get('include_disabled', '')).lower() in {"1", "true", "yes"}
        can_manage_templates = user_has_permission(
            session.get("username"),
            session.get("user_type"),
            "manage_report_templates"
        )
        include_disabled = include_disabled_requested and can_manage_templates

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            query = """
                SELECT id, key, name, description, template_json, enabled,
                       is_system, is_customized, system_revision,
                       created_by, created_at, updated_at
                FROM report_templates
            """
            if not include_disabled:
                query += " WHERE enabled = 1"
            query += " ORDER BY name COLLATE NOCASE ASC"
            c.execute(query)
            rows = c.fetchall()

        templates = [_serialize_report_template(row) for row in rows]
        return jsonify({"templates": templates}), 200
    except Exception as e:
        logger.error(f"Error fetching report templates: {e}")
        return jsonify({"error": "Failed to fetch report templates."}), 500


@permission_required('manage_report_templates')
def create_report_template():
    """POST /report-templates: Create a report template."""
    payload = request.get_json(silent=True) or {}
    normalized, validation_error = _normalize_report_template_payload(payload)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    created_by = session.get("username", "admin")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO report_templates (
                    key, name, description, template_json, enabled,
                    is_system, is_customized, system_revision,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, NULL, ?, datetime('now', '+4 hours'), datetime('now', '+4 hours'))
            """, (
                normalized["key"],
                normalized["name"],
                normalized["description"],
                normalized["template_json"],
                normalized["enabled"],
                created_by
            ))
            template_id = c.lastrowid
            conn.commit()
        return jsonify({"message": "Report template created.", "id": template_id}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "Template key already exists."}), 400
    except Exception as e:
        logger.error(f"Error creating report template: {e}")
        return jsonify({"error": "Failed to create report template."}), 500


@permission_required('manage_report_templates')
def update_report_template(template_id):
    """PUT /report-templates/<id>: Update a report template."""
    payload = request.get_json(silent=True) or {}

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT id, key, name, description, template_json, enabled,
                       is_system, is_customized
                FROM report_templates
                WHERE id = ?
            """, (template_id,))
            existing = c.fetchone()
            if not existing:
                return jsonify({"error": "Template not found."}), 404

            if payload.get("key") and bool(existing["is_system"]):
                requested_key = str(payload.get("key", "")).strip().lower()
                if requested_key and requested_key != existing["key"]:
                    return jsonify({"error": "System template key cannot be changed."}), 400

            merged_payload = {
                "key": payload.get("key", existing["key"]),
                "name": payload.get("name", existing["name"]),
                "description": payload.get("description", existing["description"]),
                "template": payload.get("template", _safe_json_load(existing["template_json"], {})),
                "enabled": payload.get("enabled", bool(existing["enabled"]))
            }
            normalized, validation_error = _normalize_report_template_payload(merged_payload)
            if validation_error:
                return jsonify({"error": validation_error}), 400

            mark_customized = 1 if bool(existing["is_system"]) else int(bool(existing["is_customized"]))
            c.execute("""
                UPDATE report_templates
                SET key = ?, name = ?, description = ?, template_json = ?, enabled = ?,
                    is_customized = ?,
                    updated_at = datetime('now', '+4 hours')
                WHERE id = ?
            """, (
                normalized["key"],
                normalized["name"],
                normalized["description"],
                normalized["template_json"],
                normalized["enabled"],
                mark_customized,
                template_id
            ))
            conn.commit()
        return jsonify({"message": "Report template updated."}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "Template key already exists."}), 400
    except Exception as e:
        logger.error(f"Error updating report template {template_id}: {e}")
        return jsonify({"error": "Failed to update report template."}), 500


@permission_required('manage_report_templates')
def delete_report_template(template_id):
    """DELETE /report-templates/<id>: Delete a report template."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT is_system FROM report_templates WHERE id = ?", (template_id,))
            existing = c.fetchone()
            if not existing:
                return jsonify({"error": "Template not found."}), 404
            if bool(existing["is_system"]):
                return jsonify({"error": "System templates cannot be deleted. Disable or reset them instead."}), 400

            c.execute("DELETE FROM report_templates WHERE id = ?", (template_id,))
            conn.commit()
        return jsonify({"message": "Report template deleted."}), 200
    except Exception as e:
        logger.error(f"Error deleting report template {template_id}: {e}")
        return jsonify({"error": "Failed to delete report template."}), 500


@permission_required('manage_report_templates')
def reset_report_template_to_canonical(template_id):
    """POST /report-templates/<id>/reset: Reset system template to canonical definition."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT id, key, is_system
                FROM report_templates
                WHERE id = ?
            """, (template_id,))
            existing = c.fetchone()
            if not existing:
                return jsonify({"error": "Template not found."}), 404
            if not bool(existing["is_system"]):
                return jsonify({"error": "Only system templates can be reset to canonical."}), 400

            canonical = get_canonical_report_template_by_key(existing["key"])
            if not canonical:
                return jsonify({"error": "Canonical template definition not found for this key."}), 404

            payload = {
                "key": canonical.get("key"),
                "name": canonical.get("name"),
                "description": canonical.get("description", ""),
                "template": canonical
            }
            normalized, validation_error = _normalize_report_template_payload(payload)
            if validation_error:
                return jsonify({"error": f"Canonical template is invalid: {validation_error}"}), 500

            system_revision = build_report_template_revision(canonical)
            c.execute("""
                UPDATE report_templates
                SET name = ?, description = ?, template_json = ?, enabled = 1,
                    is_customized = 0, system_revision = ?,
                    updated_at = datetime('now', '+4 hours')
                WHERE id = ?
            """, (
                normalized["name"],
                normalized["description"],
                normalized["template_json"],
                system_revision,
                template_id
            ))
            conn.commit()
        return jsonify({"message": "Report template reset to canonical successfully."}), 200
    except Exception as e:
        logger.error(f"Error resetting report template {template_id} to canonical: {e}")
        return jsonify({"error": "Failed to reset report template."}), 500

@permission_required('modify_pentests')
def create_or_update_pentest_data(record_id):
    """POST /pentest/<record_id>: Create or update pentest data."""
    record = get_record_details_internal(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
        row = c.fetchone()
        existing_data = dict(row) if row else {}
        
        username = session.get('username')
        role = session.get('user_type')
        can_reassign = user_has_permission(username, role, 'reassign_pentests_admin')
        can_modify_others = user_has_permission(username, role, 'modify_others_pentests_admin')

        existing_description = (record['description'] or '')
        existing_notes = existing_data.get('notes', "")
        existing_vulnerabilities = existing_data.get('vulnerabilities', "")
        old_image_filenames = _collect_referenced_image_filenames(
            existing_description,
            existing_notes,
            existing_vulnerabilities
        )

        data = {}
        for key in ['vulnerable', 'tested_by', 'test_start_date', 'test_end_date', 'vulnerability_fixed', 'service_desk_link', 'status', 'open_ports', 'notes', 'owasp_checklist', 'checklist_states', 'vulnerabilities', 'description']:
            if (value := request.form.get(key)) is not None:
                data[key] = value

        if not can_reassign and data.get('tested_by') and data.get('tested_by') != username:
            return jsonify({"error": "Unauthorized to change tester assignment."}), 403

        if not can_modify_others:
            existing_assignee = (existing_data.get('tested_by') or '').strip()
            requested_assignee = (data.get('tested_by') or existing_assignee).strip()
            if existing_assignee and existing_assignee != username:
                return jsonify({"error": "You are not allowed to change the data of another user's pentest."}), 403
            if not existing_assignee and requested_assignee != username:
                return jsonify({"error": "Unassigned records must be assigned to your user before editing."}), 403

        normalized_status = data.get('status', existing_data.get('status', 'Not Started'))
        if normalized_status not in ['Not Started', 'In Progress', 'Completed']:
            return jsonify({"error": "Invalid status. Please select from 'Not Started', 'In Progress', 'Completed."}), 400

        relative_path = existing_data.get('report_file')
        if 'report' in request.files:
            report_file = request.files['report']
            if report_file.filename != '' and report_file.filename.lower().endswith('.pdf'):
                try:
                    relative_path = save_report(record_id, report_file.read())
                    logger.debug(f"Saved report file: {relative_path}")
                except Exception as e:
                    return jsonify({"error": f"Failed to upload report: {e}"}), 500
            else:
                return jsonify({"error": "Invalid file. Please upload a PDF file."}), 400
            
        pentest_data = {
            'record_id': record_id,
            'dns_name': record['name'],
            'ip_address': record['ip_address'],
            'source': record['source'],
            'report_file': relative_path,
            'vulnerable': (
                0
                if data.get('vulnerable', existing_data.get('vulnerable', 0)) is None
                else int(data.get('vulnerable', existing_data.get('vulnerable', 0)))
            ),
            'tested_by': data.get('tested_by', existing_data.get('tested_by', '')),
            'test_start_date': data.get('test_start_date', existing_data.get('test_start_date', None)),
            'test_end_date': data.get('test_end_date', existing_data.get('test_end_date', None)),
            'vulnerability_fixed': (
                0
                if data.get('vulnerability_fixed', existing_data.get('vulnerability_fixed', 0)) is None
                else int(data.get('vulnerability_fixed', existing_data.get('vulnerability_fixed', 0)))
            ),
            'service_desk_link': data.get('service_desk_link', existing_data.get('service_desk_link', '')),
            'status': normalized_status,
            'open_ports': data.get('open_ports', existing_data.get('open_ports', "")),
            'notes': data.get('notes', existing_data.get('notes', "")),
            'owasp_checklist': data.get('owasp_checklist', existing_data.get('owasp_checklist', "")),
            'checklist_states': data.get('checklist_states', existing_data.get('checklist_states', "")),
            'vulnerabilities': data.get('vulnerabilities', existing_data.get('vulnerabilities', ""))
        }
        updated_description = data.get('description', existing_description)
        new_image_filenames = _collect_referenced_image_filenames(
            updated_description,
            pentest_data['notes'],
            pentest_data['vulnerabilities']
        )
        removed_image_filenames = old_image_filenames - new_image_filenames

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            if existing_data:
                filtered_pentest_data = {k: v for k, v in pentest_data.items() if v is not None}
                if filtered_pentest_data:
                    update_query = "UPDATE pentest_data SET " + ", ".join([f"{key} = ?" for key in filtered_pentest_data.keys()]) + " WHERE record_id = ?"
                    c.execute(update_query, list(filtered_pentest_data.values()) + [record_id])
            else:
                c.execute("""
                    INSERT INTO pentest_data (record_id, dns_name, ip_address, source, report_file, vulnerable,
                                             tested_by, test_start_date, test_end_date, vulnerability_fixed, service_desk_link, status,
                                             open_ports, notes, owasp_checklist, checklist_states, vulnerabilities)
                    VALUES (:record_id, :dns_name, :ip_address, :source, :report_file, :vulnerable,
                                             :tested_by, :test_start_date, :test_end_date, :vulnerability_fixed, :service_desk_link, :status,
                                             :open_ports, :notes, :owasp_checklist, :checklist_states, :vulnerabilities)
                """, pentest_data)

            # Sync description back to records table if provided
            if 'description' in data:
                c.execute("""
                    UPDATE records
                    SET description = ?,
                        last_modification_date = datetime('now', '+4 hours')
                    WHERE id = ?
                """, (data.get('description', ''), record_id))

            conn.commit()
        if removed_image_filenames:
            _cleanup_unreferenced_images(removed_image_filenames)

        return jsonify({"message": "Pentest data updated successfully."}), 200

    except Exception as e:
        logger.error(f"Error creating/updating pentest data for record {record_id}: {e}")
        return jsonify({"error": str(e)}), 500

@permission_required('modify_pentests')
def upload_pentest_image(record_id):
    """POST /pentest/<record_id>/images: Upload image for pentest notes/vulns."""
    record = get_record_details_internal(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    pentest_row = get_pentest_row(record_id)
    username = session.get('username')
    role = session.get('user_type')
    can_modify_others = user_has_permission(username, role, 'modify_others_pentests_admin')
    if not can_modify_others:
        if not pentest_row or pentest_row['tested_by'] != username:
            return jsonify({"error": "Unauthorized to upload images for this record."}), 403

    if 'image' not in request.files:
        return jsonify({"error": "Image file is required."}), 400
    image = request.files['image']
    if image.filename == '':
        return jsonify({"error": "Image file is required."}), 400

    extension = image.filename.rsplit('.', 1)[-1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": "Unsupported image type."}), 400

    try:
        filename = save_image(image.read(), extension)
        return jsonify({"url": f"/pentest/images/{filename}"}), 200
    except Exception as e:
        logger.error(f"Error uploading image for record {record_id}: {e}")
        return jsonify({"error": "Failed to upload image."}), 500

@permission_required('view_pentest_page')
def get_pentest_image(filename):
    """GET /pentest/images/<filename>: Serve image by filename."""
    if not re.match(r'^[a-f0-9]{32}\.(png|jpg|jpeg|gif|webp)$', filename):
        return jsonify({"error": "Invalid filename."}), 400
    if not _can_user_access_image(filename):
        return jsonify({"error": "Unauthorized access"}), 403

    extension = filename.rsplit('.', 1)[-1].lower()
    try:
        file_data = fetch_image(filename)
        return send_file(file_data, mimetype=_guess_image_mimetype(extension))
    except Exception as e:
        logger.error(f"Error fetching image {filename}: {e}")
        return jsonify({"error": "Image not found."}), 404

@permission_required('view_security_dashboard')
def get_pentest_data():
    """GET /pentest/records: Retrieve pentest data."""
    data = get_pentest_data_internal()
    if data:
        response = jsonify(data)
        status_code = 200
    else:
        response = jsonify({"error": "Pentest data not found"})
        status_code = 404

    return response, status_code


@login_required_json
@admin_required
def delete_pentest_data(record_id):
    """DELETE /pentest/<record_id>: Delete pentest data and report."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT report_file, generated_report_file
                FROM pentest_data
                WHERE record_id = ?
            """, (record_id,))
            result = c.fetchone()

            if result:
                report_file = result[0]
                generated_report_file = result[1]
                if report_file:
                    try:
                        delete_report(report_file)
                    except Exception as e:
                        return jsonify({"error": f"Failed to delete report: {e}"}), 500
                if generated_report_file:
                    try:
                        delete_report(generated_report_file)
                    except Exception as e:
                        return jsonify({"error": f"Failed to delete generated report: {e}"}), 500
                c.execute("DELETE FROM pentest_data WHERE record_id = ?", (record_id,))
                conn.commit()
                return jsonify({"message": "Pentest data deleted successfully."}), 200
            else:
                return jsonify({"error": "Pentest data not found"}), 404
    except Exception as e:
        logger.error(f"Error deleting pentest data for record {record_id}: {e}")
        return jsonify({"error": str(e)}), 500

@permission_required('view_pentest_page')
def get_report(record_id):
    """GET /pentest/<record_id>/report: Serve the PDF report."""
    allowed, denial_reason = enforce_pentest_record_access(record_id, action_verb="access report files for")
    if not allowed:
        return jsonify({"error": denial_reason}), 403

    pentest_data = get_pentest_data_internal(record_id)
    if not pentest_data or not pentest_data['report_file']:
        return jsonify({"error": "Pentest data or report file not found"}), 404

    try:
        ftp = ftp_connect()
        file_data = BytesIO()
        ftp.retrbinary(f'RETR {pentest_data["report_file"]}', file_data.write)
        ftp.quit()
        file_data.seek(0)
        return send_file(file_data, mimetype='application/pdf', as_attachment=True, download_name=f"report_{record_id}.pdf")
    except Exception as e:
        logger.error(f"Error retrieving report for record {record_id}: {e}")
        return jsonify({"error": str(e)}), 500

@permission_required('modify_pentests')
def delete_report_route(record_id):
    """DELETE /pentest/<record_id>/report: Deletes report file."""
    allowed, denial_reason = enforce_pentest_record_access(record_id, action_verb="delete report files for")
    if not allowed:
        return jsonify({"error": denial_reason}), 403

    pentest_data = get_pentest_data_internal(record_id)
    if not pentest_data or not pentest_data['report_file']:
        return jsonify({"error": "Pentest data or report file not found"}), 404

    try:
        delete_report(pentest_data["report_file"])
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE pentest_data SET report_file = NULL WHERE record_id = ?", (record_id,))
            if c.rowcount == 0:
                return jsonify({"error": f"Pentest data not found for record {record_id}"}), 404
            conn.commit()
        return jsonify({"message": "Report Deleted"}), 200
    except Exception as e:
        return jsonify({"error": f"Error deleting report: {e}"}), 500


def _load_enabled_checklist_templates():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT id, key, name, service, source, auto_ports, sections, enabled,
                   is_system, is_customized, system_revision,
                   created_by, created_at, updated_at
            FROM service_checklists
            WHERE enabled = 1
            ORDER BY name COLLATE NOCASE ASC
        """)
        return [_serialize_checklist_template(row) for row in c.fetchall()]


@permission_required('export_pentests')
def generate_report(record_id):
    """POST /pentest/<record_id>/generate-report: Generate and store a PDF report from template."""
    record = get_record_details_internal(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    allowed, denial_reason = enforce_pentest_record_access(record_id, action_verb="generate reports for")
    if not allowed:
        return jsonify({"error": denial_reason}), 403

    payload = request.get_json(silent=True) or {}
    template_id = payload.get("template_id")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            template_row = None
            if template_id is not None:
                try:
                    numeric_template_id = int(template_id)
                except (TypeError, ValueError):
                    return jsonify({"error": "Template id must be an integer."}), 400
                c.execute("""
                    SELECT id, key, name, description, template_json, enabled
                    FROM report_templates
                    WHERE id = ?
                """, (numeric_template_id,))
                template_row = c.fetchone()
                if not template_row:
                    return jsonify({"error": "Report template not found."}), 404
                if int(template_row["enabled"] or 0) != 1 and session.get("user_type") != "admin":
                    return jsonify({"error": "Selected report template is disabled."}), 400
            else:
                c.execute("""
                    SELECT id, key, name, description, template_json, enabled
                    FROM report_templates
                    WHERE enabled = 1
                    ORDER BY name COLLATE NOCASE ASC
                    LIMIT 1
                """)
                template_row = c.fetchone()
                if not template_row:
                    return jsonify({"error": "No enabled report template available."}), 404

            template_definition = _safe_json_load(template_row["template_json"], {})
            if not isinstance(template_definition, dict):
                return jsonify({"error": "Report template definition is invalid."}), 500

            checklist_templates = _load_enabled_checklist_templates()
            pentest_data = get_pentest_data_internal(record_id)
            if not pentest_data:
                return jsonify({"error": "Pentest data not found."}), 404

            pdf_content = render_pentest_report_pdf(
                pentest_data,
                template_definition,
                checklist_templates=checklist_templates,
                image_fetcher=fetch_image
            )
            generated_relative_path = save_report(record_id, pdf_content)

            c.execute("""
                SELECT generated_report_file
                FROM pentest_data
                WHERE record_id = ?
            """, (record_id,))
            existing_generated = c.fetchone()
            previous_generated_path = existing_generated["generated_report_file"] if existing_generated else None

            if existing_generated:
                c.execute("""
                    UPDATE pentest_data
                    SET generated_report_file = ?,
                        generated_report_template_id = ?,
                        generated_report_generated_at = datetime('now', '+4 hours')
                    WHERE record_id = ?
                """, (generated_relative_path, template_row["id"], record_id))
            else:
                c.execute("""
                    INSERT INTO pentest_data (
                        record_id, dns_name, ip_address, source,
                        generated_report_file, generated_report_template_id, generated_report_generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+4 hours'))
                """, (
                    record_id,
                    record['name'],
                    record['ip_address'],
                    record['source'],
                    generated_relative_path,
                    template_row["id"]
                ))
            conn.commit()

        if previous_generated_path and previous_generated_path != generated_relative_path:
            try:
                delete_report(previous_generated_path)
            except Exception as e:
                logger.warning(f"Failed to delete previous generated report '{previous_generated_path}': {e}")

        return jsonify({
            "message": "Report generated successfully.",
            "report_file": generated_relative_path,
            "template_id": template_row["id"],
            "template_key": template_row["key"],
            "template_name": template_row["name"]
        }), 200
    except Exception as e:
        logger.error(f"Error generating report for record {record_id}: {e}")
        return jsonify({"error": "Failed to generate report."}), 500


@permission_required('export_pentests')
def get_generated_report(record_id):
    """GET /pentest/<record_id>/generated-report: Serve generated PDF report."""
    allowed, denial_reason = enforce_pentest_record_access(record_id, action_verb="access generated reports for")
    if not allowed:
        return jsonify({"error": denial_reason}), 403

    pentest_data = get_pentest_data_internal(record_id)
    if not pentest_data or not pentest_data.get('generated_report_file'):
        return jsonify({"error": "Generated report not found"}), 404

    try:
        ftp = ftp_connect()
        file_data = BytesIO()
        ftp.retrbinary(f'RETR {pentest_data["generated_report_file"]}', file_data.write)
        ftp.quit()
        file_data.seek(0)
        return send_file(
            file_data,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"generated_report_{record_id}.pdf"
        )
    except Exception as e:
        logger.error(f"Error retrieving generated report for record {record_id}: {e}")
        return jsonify({"error": "Failed to retrieve generated report."}), 500


@permission_required('modify_pentests')
def delete_generated_report_route(record_id):
    """DELETE /pentest/<record_id>/generated-report: Delete generated report file."""
    allowed, denial_reason = enforce_pentest_record_access(record_id, action_verb="delete generated reports for")
    if not allowed:
        return jsonify({"error": denial_reason}), 403

    pentest_data = get_pentest_data_internal(record_id)
    if not pentest_data or not pentest_data.get('generated_report_file'):
        return jsonify({"error": "Generated report not found"}), 404

    try:
        delete_report(pentest_data["generated_report_file"])
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE pentest_data
                SET generated_report_file = NULL,
                    generated_report_template_id = NULL,
                    generated_report_generated_at = NULL
                WHERE record_id = ?
            """, (record_id,))
            if c.rowcount == 0:
                return jsonify({"error": f"Pentest data not found for record {record_id}"}), 404
            conn.commit()
        return jsonify({"message": "Generated report deleted."}), 200
    except Exception as e:
        return jsonify({"error": f"Error deleting generated report: {e}"}), 500
