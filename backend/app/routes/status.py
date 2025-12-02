import sqlite3
import logging
from flask import Blueprint, jsonify
from ..services.auth import login_required_json
from ..config import DB_PATH

logger = logging.getLogger(__name__)

status_bp = Blueprint("status", __name__)


@status_bp.route("/api/system-status", methods=["GET"])
@login_required_json
def get_system_status():
    """
    Get system status for all services.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM system_status ORDER BY service_name")
        rows = c.fetchall()
        conn.close()

        status_data = {}
        for row in rows:
            status_data[row["service_name"]] = {
                "status": row["status"],
                "message": row["message"],
                "details": row["details"],
                "last_updated": row["last_updated"],
            }

        return jsonify(status_data)

    except Exception as e:
        logger.error("Error getting system status: %s", e)
        return jsonify({"error": "Failed to get system status"}), 500


@status_bp.route("/api/system-status/<service_name>", methods=["GET"])
@login_required_json
def get_service_status(service_name):
    """
    Get status for a specific service.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM system_status WHERE service_name = ?", (service_name,))
        row = c.fetchone()
        conn.close()

        if row:
            return jsonify(
                {
                    "status": row["status"],
                    "message": row["message"],
                    "details": row["details"],
                    "last_updated": row["last_updated"],
                }
            )
        return jsonify({"error": "Service not found"}), 404

    except Exception as e:
        logger.error("Error getting service status: %s", e)
        return jsonify({"error": "Failed to get service status"}), 500
