import logging
import re
import json
from app.integrations.db.connection import IntegrityError, ROW_AS_DICT, get_db_connection

from flask import jsonify, request, session

from app.http.decorators.admin_required import admin_required
from app.http.decorators.permission_required import permission_required
from app.domain.offsec.shared import (
    DB_PATH,
    build_checklist_revision,
    build_report_template_revision,
    get_canonical_checklist_by_key,
    get_canonical_report_template_by_key,
    normalize_checklist_template_payload,
    normalize_report_template_payload,
    safe_json_load,
    serialize_checklist_template,
    serialize_report_template,
)
from app.services.authorization_service import user_has_permission
from app.integrations.storage.offsec_storage import save_image

logger = logging.getLogger(__name__)

MAX_REPORT_LOGO_BYTES = 2 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_IHDR_MARKER = b"IHDR"
PNG_FILENAME_PATTERN = re.compile(r".+\.png$", re.IGNORECASE)


def _is_valid_png(file_data):
    if not file_data or len(file_data) < 24:
        return False
    if not file_data.startswith(PNG_SIGNATURE):
        return False
    return file_data[12:16] == PNG_IHDR_MARKER


def _validate_report_logo_file(file_storage):
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None, "Logo file is required."
    if not PNG_FILENAME_PATTERN.match(str(file_storage.filename).strip()):
        return None, "Only PNG logo files are allowed."

    file_data = file_storage.read(MAX_REPORT_LOGO_BYTES + 1)
    if not file_data:
        return None, "Logo file is required."
    if len(file_data) > MAX_REPORT_LOGO_BYTES:
        return None, "Logo file is too large. Max size is 2 MB."
    if not _is_valid_png(file_data):
        return None, "Invalid PNG file."
    return file_data, None


def _extract_logo_asset_id(template_definition):
    if not isinstance(template_definition, dict):
        return None, "Template definition is invalid."
    branding = template_definition.get("branding")
    if not isinstance(branding, dict):
        return None, None
    raw_logo_asset_id = branding.get("logo_asset_id")
    if raw_logo_asset_id is None or str(raw_logo_asset_id).strip() == "":
        return None, None
    try:
        logo_asset_id = int(raw_logo_asset_id)
    except (TypeError, ValueError):
        return None, "Logo asset id must be a positive integer."
    if logo_asset_id <= 0:
        return None, "Logo asset id must be a positive integer."
    return logo_asset_id, None


def _set_logo_branding(template_definition, logo_asset_id, logo_url):
    next_definition = dict(template_definition or {})
    existing_branding = next_definition.get("branding")
    branding = dict(existing_branding) if isinstance(existing_branding, dict) else {}
    branding["logo_asset_id"] = logo_asset_id
    branding["logo_url"] = logo_url
    next_definition["branding"] = branding
    return next_definition


def _get_logo_file_path(cursor, template_id, logo_asset_id):
    cursor.execute(
        """
        SELECT file_path
        FROM report_template_logo_assets
        WHERE id = ? AND report_template_id = ?
        """,
        (logo_asset_id, template_id),
    )
    row = cursor.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return str(row.get("file_path") or "").strip()
    return str(row[0] or "").strip()


def prepare_report_template_logo_for_create(template_definition):
    logo_asset_id, logo_error = _extract_logo_asset_id(template_definition)
    if logo_error:
        return None, logo_error
    if logo_asset_id is not None:
        return None, "Save template first, then upload/select a logo for it."
    return _set_logo_branding(template_definition, None, ""), None


def bind_report_template_logo_for_template(cursor, template_id, template_definition):
    logo_asset_id, logo_error = _extract_logo_asset_id(template_definition)
    if logo_error:
        return None, logo_error
    if logo_asset_id is None:
        return _set_logo_branding(template_definition, None, ""), None

    logo_file_path = _get_logo_file_path(cursor, template_id, logo_asset_id)
    if not logo_file_path:
        return None, "Invalid logo asset for this report template."
    return _set_logo_branding(template_definition, logo_asset_id, f"/pentest/images/{logo_file_path}"), None


@permission_required("view_pentest_page")
def get_checklist_templates():
    """GET /checklist-templates: List checklist templates."""
    try:
        include_disabled_requested = str(request.args.get("include_disabled", "")).lower() in {
            "1",
            "true",
            "yes",
        }
        include_disabled = include_disabled_requested and session.get("user_type") == "admin"

        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            query = """
                SELECT id, key, name, service, source, auto_ports, sections, enabled,
                       is_system, is_customized, system_revision,
                       created_by, created_at, updated_at
                FROM service_checklists
            """
            if not include_disabled:
                query += " WHERE enabled = 1"
            query += " ORDER BY LOWER(name) ASC"
            c.execute(query)
            rows = c.fetchall()
        templates = [serialize_checklist_template(row) for row in rows]
        return jsonify({"templates": templates}), 200
    except Exception as e:
        logger.error(f"Error fetching checklist templates: {e}")
        return jsonify({"error": "Failed to fetch checklist templates."}), 500


@admin_required
def create_checklist_template():
    """POST /checklist-templates: Create a checklist template."""
    payload = request.get_json(silent=True) or {}
    normalized, validation_error = normalize_checklist_template_payload(payload)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    created_by = session.get("username", "admin")
    try:
        with get_db_connection(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO service_checklists (
                    key, name, service, source, auto_ports, sections, enabled,
                    is_system, is_customized, system_revision,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, ?, (NOW() + INTERVAL '4 hours'), (NOW() + INTERVAL '4 hours'))
                RETURNING id
                """,
                (
                    normalized["key"],
                    normalized["name"],
                    normalized["service"],
                    normalized["source"],
                    normalized["auto_ports"],
                    normalized["sections"],
                    normalized["enabled"],
                    created_by,
                ),
            )
            inserted = c.fetchone()
            template_id = inserted[0] if inserted else None
            if template_id is None:
                raise RuntimeError("Failed to create checklist template.")
            conn.commit()
        return jsonify({"message": "Checklist template created.", "id": template_id}), 200
    except IntegrityError:
        return jsonify({"error": "Template key already exists."}), 400
    except Exception as e:
        logger.error(f"Error creating checklist template: {e}")
        return jsonify({"error": "Failed to create checklist template."}), 500


@admin_required
def update_checklist_template(template_id):
    """PUT /checklist-templates/<id>: Update a checklist template."""
    payload = request.get_json(silent=True) or {}

    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute(
                """
                SELECT id, key, name, service, source, auto_ports, sections, enabled,
                       is_system, is_customized, system_revision
                FROM service_checklists
                WHERE id = ?
                """,
                (template_id,),
            )
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
                "auto_ports": payload.get("auto_ports", safe_json_load(existing["auto_ports"], [])),
                "sections": payload.get("sections", safe_json_load(existing["sections"], [])),
                "enabled": payload.get("enabled", bool(existing["enabled"])),
            }

            normalized, validation_error = normalize_checklist_template_payload(merged_payload)
            if validation_error:
                return jsonify({"error": validation_error}), 400

            mark_customized = 1 if bool(existing["is_system"]) else int(bool(existing["is_customized"]))
            c.execute(
                """
                UPDATE service_checklists
                SET key = ?, name = ?, service = ?, source = ?, auto_ports = ?, sections = ?, enabled = ?,
                    is_customized = ?,
                    updated_at = (NOW() + INTERVAL '4 hours')
                WHERE id = ?
                """,
                (
                    normalized["key"],
                    normalized["name"],
                    normalized["service"],
                    normalized["source"],
                    normalized["auto_ports"],
                    normalized["sections"],
                    normalized["enabled"],
                    mark_customized,
                    template_id,
                ),
            )
            conn.commit()
        return jsonify({"message": "Checklist template updated."}), 200
    except IntegrityError:
        return jsonify({"error": "Template key already exists."}), 400
    except Exception as e:
        logger.error(f"Error updating checklist template {template_id}: {e}")
        return jsonify({"error": "Failed to update checklist template."}), 500


@admin_required
def delete_checklist_template(template_id):
    """DELETE /checklist-templates/<id>: Delete a checklist template."""
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
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
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute(
                """
                SELECT id, key, is_system
                FROM service_checklists
                WHERE id = ?
                """,
                (template_id,),
            )
            existing = c.fetchone()
            if not existing:
                return jsonify({"error": "Template not found."}), 404
            if not bool(existing["is_system"]):
                return jsonify({"error": "Only system templates can be reset to canonical."}), 400

            canonical = get_canonical_checklist_by_key(existing["key"])
            if not canonical:
                return jsonify({"error": "Canonical template definition not found for this key."}), 404

            normalized, validation_error = normalize_checklist_template_payload(canonical)
            if validation_error:
                return jsonify({"error": f"Canonical template is invalid: {validation_error}"}), 500

            system_revision = build_checklist_revision(canonical)
            c.execute(
                """
                UPDATE service_checklists
                SET name = ?, service = ?, source = ?, auto_ports = ?, sections = ?, enabled = 1,
                    is_customized = 0, system_revision = ?,
                    updated_at = (NOW() + INTERVAL '4 hours')
                WHERE id = ?
                """,
                (
                    normalized["name"],
                    normalized["service"],
                    normalized["source"],
                    normalized["auto_ports"],
                    normalized["sections"],
                    system_revision,
                    template_id,
                ),
            )
            conn.commit()
        return jsonify({"message": "Checklist template reset to canonical successfully."}), 200
    except Exception as e:
        logger.error(f"Error resetting checklist template {template_id} to canonical: {e}")
        return jsonify({"error": "Failed to reset checklist template."}), 500


@permission_required("view_pentest_page")
def get_report_templates():
    """GET /report-templates: List report templates."""
    try:
        include_disabled_requested = str(request.args.get("include_disabled", "")).lower() in {
            "1",
            "true",
            "yes",
        }
        can_manage_templates = user_has_permission(
            session.get("username"),
            session.get("user_type"),
            "manage_report_templates",
        )
        include_disabled = include_disabled_requested and can_manage_templates

        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            query = """
                SELECT id, key, name, description, template_json, enabled,
                       is_system, is_customized, system_revision,
                       created_by, created_at, updated_at
                FROM report_templates
            """
            if not include_disabled:
                query += " WHERE enabled = 1"
            query += " ORDER BY LOWER(name) ASC"
            c.execute(query)
            rows = c.fetchall()

        templates = [serialize_report_template(row) for row in rows]
        return jsonify({"templates": templates}), 200
    except Exception as e:
        logger.error(f"Error fetching report templates: {e}")
        return jsonify({"error": "Failed to fetch report templates."}), 500


@permission_required("manage_report_templates")
def create_report_template():
    """POST /report-templates: Create a report template."""
    payload = request.get_json(silent=True) or {}
    normalized, validation_error = normalize_report_template_payload(payload)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    created_by = session.get("username", "admin")
    try:
        with get_db_connection(DB_PATH) as conn:
            c = conn.cursor()
            template_definition = safe_json_load(normalized["template_json"], {})
            template_definition, logo_error = prepare_report_template_logo_for_create(template_definition)
            if logo_error:
                return jsonify({"error": logo_error}), 400
            normalized["template_json"] = json.dumps(template_definition)

            c.execute(
                """
                INSERT INTO report_templates (
                    key, name, description, template_json, enabled,
                    is_system, is_customized, system_revision,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, NULL, ?, (NOW() + INTERVAL '4 hours'), (NOW() + INTERVAL '4 hours'))
                RETURNING id
                """,
                (
                    normalized["key"],
                    normalized["name"],
                    normalized["description"],
                    normalized["template_json"],
                    normalized["enabled"],
                    created_by,
                ),
            )
            inserted = c.fetchone()
            template_id = inserted[0] if inserted else None
            if template_id is None:
                raise RuntimeError("Failed to create report template.")
            conn.commit()
        return jsonify({"message": "Report template created.", "id": template_id}), 200
    except IntegrityError:
        return jsonify({"error": "Template key already exists."}), 400
    except Exception as e:
        logger.error(f"Error creating report template: {e}")
        return jsonify({"error": "Failed to create report template."}), 500


@permission_required("manage_report_templates")
def update_report_template(template_id):
    """PUT /report-templates/<id>: Update a report template."""
    payload = request.get_json(silent=True) or {}

    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute(
                """
                SELECT id, key, name, description, template_json, enabled,
                       is_system, is_customized
                FROM report_templates
                WHERE id = ?
                """,
                (template_id,),
            )
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
                "template": payload.get("template", safe_json_load(existing["template_json"], {})),
                "enabled": payload.get("enabled", bool(existing["enabled"])),
            }
            normalized, validation_error = normalize_report_template_payload(merged_payload)
            if validation_error:
                return jsonify({"error": validation_error}), 400

            template_definition = safe_json_load(normalized["template_json"], {})
            template_definition, logo_error = bind_report_template_logo_for_template(
                c,
                template_id,
                template_definition,
            )
            if logo_error:
                return jsonify({"error": logo_error}), 400
            normalized["template_json"] = json.dumps(template_definition)

            mark_customized = 1 if bool(existing["is_system"]) else int(bool(existing["is_customized"]))
            c.execute(
                """
                UPDATE report_templates
                SET key = ?, name = ?, description = ?, template_json = ?, enabled = ?,
                    is_customized = ?,
                    updated_at = (NOW() + INTERVAL '4 hours')
                WHERE id = ?
                """,
                (
                    normalized["key"],
                    normalized["name"],
                    normalized["description"],
                    normalized["template_json"],
                    normalized["enabled"],
                    mark_customized,
                    template_id,
                ),
            )
            conn.commit()
        return jsonify({"message": "Report template updated."}), 200
    except IntegrityError:
        return jsonify({"error": "Template key already exists."}), 400
    except Exception as e:
        logger.error(f"Error updating report template {template_id}: {e}")
        return jsonify({"error": "Failed to update report template."}), 500


@permission_required("manage_report_templates")
def delete_report_template(template_id):
    """DELETE /report-templates/<id>: Delete a report template."""
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
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


@permission_required("manage_report_templates")
def reset_report_template_to_canonical(template_id):
    """POST /report-templates/<id>/reset: Reset system template to canonical definition."""
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute(
                """
                SELECT id, key, is_system
                FROM report_templates
                WHERE id = ?
                """,
                (template_id,),
            )
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
                "template": canonical,
            }
            normalized, validation_error = normalize_report_template_payload(payload)
            if validation_error:
                return jsonify({"error": f"Canonical template is invalid: {validation_error}"}), 500
            template_definition = safe_json_load(normalized["template_json"], {})
            template_definition = _set_logo_branding(template_definition, None, "")
            normalized["template_json"] = json.dumps(template_definition)

            system_revision = build_report_template_revision(canonical)
            c.execute(
                """
                UPDATE report_templates
                SET name = ?, description = ?, template_json = ?, enabled = 1,
                    is_customized = 0, system_revision = ?,
                    updated_at = (NOW() + INTERVAL '4 hours')
                WHERE id = ?
                """,
                (
                    normalized["name"],
                    normalized["description"],
                    normalized["template_json"],
                    system_revision,
                    template_id,
                ),
            )
            conn.commit()
        return jsonify({"message": "Report template reset to canonical successfully."}), 200
    except Exception as e:
        logger.error(f"Error resetting report template {template_id} to canonical: {e}")
        return jsonify({"error": "Failed to reset report template."}), 500


@permission_required("manage_report_templates")
def upload_report_template_logo():
    """POST /report-templates/logo-upload: Upload a PNG logo for report templates."""
    raw_template_id = request.form.get("template_id")
    try:
        template_id = int(raw_template_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Template id is required."}), 400
    if template_id <= 0:
        return jsonify({"error": "Template id is required."}), 400

    logo_file = request.files.get("logo")
    file_data, validation_error = _validate_report_logo_file(logo_file)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute("SELECT id FROM report_templates WHERE id = ?", (template_id,))
            existing_template = c.fetchone()
            if not existing_template:
                return jsonify({"error": "Template not found."}), 404

            filename = save_image(file_data, "png")

            c.execute(
                """
                INSERT INTO report_template_logo_assets (
                    report_template_id, file_path, created_by, created_at
                ) VALUES (?, ?, ?, (NOW() + INTERVAL '4 hours'))
                RETURNING id
                """,
                (template_id, filename, session.get("username", "admin")),
            )
            inserted = c.fetchone()
            logo_asset_id = inserted["id"] if isinstance(inserted, dict) else inserted[0]
            conn.commit()

        return jsonify({"logo_asset_id": logo_asset_id, "logo_url": f"/pentest/images/{filename}"}), 200
    except Exception as e:
        logger.error(f"Error uploading report template logo: {e}")
        return jsonify({"error": "Failed to upload logo."}), 500


__all__ = [
    "create_checklist_template",
    "create_report_template",
    "delete_checklist_template",
    "delete_report_template",
    "get_checklist_templates",
    "get_report_templates",
    "bind_report_template_logo_for_template",
    "prepare_report_template_logo_for_create",
    "reset_checklist_template_to_canonical",
    "reset_report_template_to_canonical",
    "upload_report_template_logo",
    "update_checklist_template",
    "update_report_template",
]
