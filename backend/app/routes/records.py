import re
import sqlite3
import logging
from flask import Blueprint, jsonify, request, session
from ..services.auth import login_required_json
from ..services.admin import admin_required
from ..config import DB_PATH

logger = logging.getLogger(__name__)

records_bp = Blueprint("records", __name__)


@records_bp.route("/api/records", methods=["GET"])
@login_required_json
def get_records():
    """
    Returns all records from the database with pentest data (including open_ports).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT r.*, p.report_file, p.vulnerable, p.tested_by, p.test_start_date, p.test_end_date,
               p.vulnerability_fixed, p.service_desk_link, p.status, p.open_ports, p.notes, p.owasp_checklist
        FROM records r
        LEFT JOIN pentest_data p ON r.id = p.record_id
    """
    )
    rows = c.fetchall()
    conn.close()

    records = [dict(ix) for ix in rows]
    return jsonify(records)


@records_bp.route("/api/records/<int:record_id>", methods=["POST"])
@login_required_json
def update_record(record_id):
    """
    Update a record by ID (including open_ports in pentest_data).
    """
    data = request.get_json(force=True)

    def sanitize_string(s):
        return re.sub(r"[^a-zA-Z0-9\.\-_ ]+", "", s)

    try:
        application_owner = sanitize_string(data.get("application_owner", ""))
        maintainer = sanitize_string(data.get("maintainer", ""))
        open_ports = data.get("open_ports", "")
        description = data.get("description", "")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT maintainer FROM records WHERE id = ?", (record_id,))
        old_record = c.fetchone()
        if not old_record:
            conn.close()
            return jsonify({"error": "Record not found"}), 404

        old_maintainer = old_record[0]

        c.execute(
            """
            UPDATE records
            SET application_owner = ?,
                maintainer = ?,
                description = ?,
                last_modification_date = datetime('now', '+4 hours')
            WHERE id = ?
        """,
            (application_owner, maintainer, description, record_id),
        )

        c.execute("SELECT record_id FROM pentest_data WHERE record_id = ?", (record_id,))
        pentest_exists = c.fetchone()

        if pentest_exists:
            c.execute(
                """
                UPDATE pentest_data
                SET open_ports = ?
                WHERE record_id = ?
            """,
                (open_ports, record_id),
            )
        else:
            c.execute("SELECT name, ip_address, source FROM records WHERE id = ?", (record_id,))
            record_info = c.fetchone()
            if record_info:
                c.execute(
                    """
                    INSERT INTO pentest_data (record_id, dns_name, ip_address, source, open_ports)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (record_id, record_info[0], record_info[1], record_info[2], open_ports),
                )

        if old_maintainer != maintainer:
            c.execute(
                """
                INSERT INTO record_history (record_id, action, timestamp, username,
                                           old_ip_address, new_ip_address,
                                           old_source, new_source,
                                           old_maintainer, new_maintainer)
                VALUES (?, 'updated', datetime('now', '+4 hours'), ?,
                        NULL, NULL,
                        NULL, NULL,
                        ?, ?)
            """,
                (record_id, session["username"], old_maintainer, maintainer),
            )

        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error("Error updating record %s: %s", record_id, e)
        return jsonify({"error": str(e)}), 400


@records_bp.route("/api/records/<int:record_id>", methods=["DELETE"])
@admin_required
def delete_record(record_id):
    """
    Delete a record by ID.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT ip_address, source, maintainer FROM records WHERE id = ?", (record_id,))
        record_data = c.fetchone()
        if not record_data:
            conn.close()
            return jsonify({"error": "Record not found"}), 404

        old_ip_address, old_source, old_maintainer = record_data

        c.execute(
            """
            INSERT INTO record_history (record_id, action, timestamp, username,
                                       old_ip_address, new_ip_address,
                                       old_source, new_source,
                                       old_maintainer, new_maintainer)
            VALUES (?, 'deleted', datetime('now', '+4 hours'), ?,
                    ?, NULL,
                    ?, NULL,
                    ?, NULL)
        """,
            (record_id, session["username"], old_ip_address, old_source, old_maintainer),
        )

        c.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Record {record_id} deleted"}), 200
    except Exception as e:
        logger.error("Error deleting record %s: %s", record_id, e)
        return jsonify({"status": "error", "message": str(e)}), 400


@records_bp.route("/api/records/<int:record_id>/history", methods=["GET"])
@login_required_json
def get_record_history(record_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM record_history WHERE record_id = ? ORDER BY timestamp DESC", (record_id,))
    rows = c.fetchall()
    conn.close()

    history = [dict(ix) for ix in rows]
    return jsonify(history)


@records_bp.route("/api/records/<string:domain>", methods=["GET"])
@login_required_json
def get_record_by_domain(domain):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT r.*, p.open_ports
        FROM records r
        LEFT JOIN pentest_data p ON r.id = p.record_id
        WHERE r.name = ?
    """,
        (domain,),
    )
    row = c.fetchone()
    conn.close()

    if row:
        record = dict(row)
        return jsonify(record)
    return jsonify({"error": "Record not found"}), 404
