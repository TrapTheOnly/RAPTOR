import logging
from typing import Any, Dict, Tuple

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.integrations.storage.offsec_storage import delete_report

logger = logging.getLogger(__name__)


def reset_keep_open_vulnerabilities(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    confirm = data.get("confirm") is True
    phrase = data.get("phrase")
    required_phrase = "RESET ALL BUT OPEN VULNERABILITIES"
    if not confirm or phrase != required_phrase:
        return {"error": "Confirmation phrase required."}, 400

    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()

            c.execute(
                """
                SELECT p.*
                FROM pentest_data p
                WHERE NOT (p.vulnerable = 1 AND p.vulnerability_fixed = 0)
                """
            )
            rows = c.fetchall()

            report_deleted = 0
            report_delete_errors = 0
            generated_report_deleted = 0
            generated_report_delete_errors = 0

            for row in rows:
                if row["report_file"]:
                    try:
                        delete_report(row["report_file"])
                        report_deleted += 1
                    except Exception:
                        report_delete_errors += 1
                if "generated_report_file" in row.keys() and row["generated_report_file"]:
                    try:
                        delete_report(row["generated_report_file"])
                        generated_report_deleted += 1
                    except Exception:
                        generated_report_delete_errors += 1

            c.execute(
                """
                DELETE FROM pentest_data
                WHERE NOT (vulnerable = 1 AND vulnerability_fixed = 0)
                """
            )
            deleted_count = c.rowcount

            c.execute(
                """
                SELECT COUNT(*)
                FROM pentest_data
                WHERE vulnerable = 1 AND vulnerability_fixed = 0
                """
            )
            remaining_open = c.fetchone()[0]

            conn.commit()

        stats = {
            "total_reset": deleted_count,
            "remaining_open": remaining_open,
            "reports_deleted": report_deleted,
            "report_delete_errors": report_delete_errors,
            "generated_reports_deleted": generated_report_deleted,
            "generated_report_delete_errors": generated_report_delete_errors,
        }

        return {
            "message": "Pentest progress reset (open vulnerabilities preserved).",
            "stats": stats,
        }, 200
    except Exception as e:
        logger.error(f"Error resetting pentest progress: {e}")
        return {"error": "Failed to reset pentest progress."}, 500
