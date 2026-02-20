import logging
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

logger = logging.getLogger(__name__)


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


__all__ = [
    "create_checklist_template",
    "create_report_template",
    "delete_checklist_template",
    "delete_report_template",
    "get_checklist_templates",
    "get_report_templates",
    "reset_checklist_template_to_canonical",
    "reset_report_template_to_canonical",
    "update_checklist_template",
    "update_report_template",
]
