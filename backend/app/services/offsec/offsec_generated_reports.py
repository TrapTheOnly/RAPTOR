import logging
import sqlite3
from io import BytesIO

from flask import jsonify, request, send_file, session

from app.repositories.offsec.offsec_records import (
    enforce_pentest_record_access,
    get_pentest_data_internal,
    get_record_details_internal,
)
from app.domain.offsec.shared import DB_PATH, safe_json_load, serialize_checklist_template
from app.integrations.storage.offsec_storage import delete_report, fetch_image, ftp_connect, save_report
from app.http.decorators.permission_required import permission_required
from app.integrations.reporting.report_pdf_render import render_pentest_report_pdf

logger = logging.getLogger(__name__)


def load_enabled_checklist_templates():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT id, key, name, service, source, auto_ports, sections, enabled,
                   is_system, is_customized, system_revision,
                   created_by, created_at, updated_at
            FROM service_checklists
            WHERE enabled = 1
            ORDER BY name COLLATE NOCASE ASC
            """
        )
        return [serialize_checklist_template(row) for row in c.fetchall()]


@permission_required("export_pentests")
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
                c.execute(
                    """
                    SELECT id, key, name, description, template_json, enabled
                    FROM report_templates
                    WHERE id = ?
                    """,
                    (numeric_template_id,),
                )
                template_row = c.fetchone()
                if not template_row:
                    return jsonify({"error": "Report template not found."}), 404
                if int(template_row["enabled"] or 0) != 1 and session.get("user_type") != "admin":
                    return jsonify({"error": "Selected report template is disabled."}), 400
            else:
                c.execute(
                    """
                    SELECT id, key, name, description, template_json, enabled
                    FROM report_templates
                    WHERE enabled = 1
                    ORDER BY name COLLATE NOCASE ASC
                    LIMIT 1
                    """
                )
                template_row = c.fetchone()
                if not template_row:
                    return jsonify({"error": "No enabled report template available."}), 404

            template_definition = safe_json_load(template_row["template_json"], {})
            if not isinstance(template_definition, dict):
                return jsonify({"error": "Report template definition is invalid."}), 500

            checklist_templates = load_enabled_checklist_templates()
            pentest_data = get_pentest_data_internal(record_id)
            if not pentest_data:
                return jsonify({"error": "Pentest data not found."}), 404

            pdf_content = render_pentest_report_pdf(
                pentest_data,
                template_definition,
                checklist_templates=checklist_templates,
                image_fetcher=fetch_image,
            )
            generated_relative_path = save_report(record_id, pdf_content)

            c.execute(
                """
                SELECT generated_report_file
                FROM pentest_data
                WHERE record_id = ?
                """,
                (record_id,),
            )
            existing_generated = c.fetchone()
            previous_generated_path = existing_generated["generated_report_file"] if existing_generated else None

            if existing_generated:
                c.execute(
                    """
                    UPDATE pentest_data
                    SET generated_report_file = ?,
                        generated_report_template_id = ?,
                        generated_report_generated_at = datetime('now', '+4 hours')
                    WHERE record_id = ?
                    """,
                    (generated_relative_path, template_row["id"], record_id),
                )
            else:
                c.execute(
                    """
                    INSERT INTO pentest_data (
                        record_id, dns_name, ip_address, source,
                        generated_report_file, generated_report_template_id, generated_report_generated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+4 hours'))
                    """,
                    (
                        record_id,
                        record["name"],
                        record["ip_address"],
                        record["source"],
                        generated_relative_path,
                        template_row["id"],
                    ),
                )
            conn.commit()

        if previous_generated_path and previous_generated_path != generated_relative_path:
            try:
                delete_report(previous_generated_path)
            except Exception as e:
                logger.warning(f"Failed to delete previous generated report '{previous_generated_path}': {e}")

        return (
            jsonify(
                {
                    "message": "Report generated successfully.",
                    "report_file": generated_relative_path,
                    "template_id": template_row["id"],
                    "template_key": template_row["key"],
                    "template_name": template_row["name"],
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error generating report for record {record_id}: {e}")
        return jsonify({"error": "Failed to generate report."}), 500


@permission_required("export_pentests")
def get_generated_report(record_id):
    """GET /pentest/<record_id>/generated-report: Serve generated PDF report."""
    allowed, denial_reason = enforce_pentest_record_access(record_id, action_verb="access generated reports for")
    if not allowed:
        return jsonify({"error": denial_reason}), 403

    pentest_data = get_pentest_data_internal(record_id)
    if not pentest_data or not pentest_data.get("generated_report_file"):
        return jsonify({"error": "Generated report not found"}), 404

    try:
        ftp = ftp_connect()
        file_data = BytesIO()
        ftp.retrbinary(f"RETR {pentest_data['generated_report_file']}", file_data.write)
        ftp.quit()
        file_data.seek(0)
        return send_file(
            file_data,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"generated_report_{record_id}.pdf",
        )
    except Exception as e:
        logger.error(f"Error retrieving generated report for record {record_id}: {e}")
        return jsonify({"error": "Failed to retrieve generated report."}), 500


@permission_required("modify_pentests")
def delete_generated_report_route(record_id):
    """DELETE /pentest/<record_id>/generated-report: Delete generated report file."""
    allowed, denial_reason = enforce_pentest_record_access(record_id, action_verb="delete generated reports for")
    if not allowed:
        return jsonify({"error": denial_reason}), 403

    pentest_data = get_pentest_data_internal(record_id)
    if not pentest_data or not pentest_data.get("generated_report_file"):
        return jsonify({"error": "Generated report not found"}), 404

    try:
        delete_report(pentest_data["generated_report_file"])
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                """
                UPDATE pentest_data
                SET generated_report_file = NULL,
                    generated_report_template_id = NULL,
                    generated_report_generated_at = NULL
                WHERE record_id = ?
                """,
                (record_id,),
            )
            if c.rowcount == 0:
                return jsonify({"error": f"Pentest data not found for record {record_id}"}), 404
            conn.commit()
        return jsonify({"message": "Generated report deleted."}), 200
    except Exception as e:
        logger.error(f"Error deleting generated report for record {record_id}: {e}")
        return jsonify({"error": "Failed to delete generated report."}), 500


__all__ = [
    "delete_generated_report_route",
    "generate_report",
    "get_generated_report",
    "load_enabled_checklist_templates",
]
