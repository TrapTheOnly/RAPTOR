import logging
from typing import Any, Dict, Tuple

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

logger = logging.getLogger(__name__)

REQUIRED_RESET_PHRASE = "RESET NOTEBOOKS KEEP FINDINGS"


def reset_keep_open_vulnerabilities(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    confirm = data.get("confirm") is True
    phrase = data.get("phrase")
    if not confirm or phrase != REQUIRED_RESET_PHRASE:
        return {"error": "Confirmation phrase required."}, 400

    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute(
                """
                UPDATE pentest_data
                SET status = 'Not Started',
                    notes = '',
                    owasp_checklist = NULL,
                    checklist_states = NULL,
                    open_ports = COALESCE(open_ports, ''),
                    tested_by = NULL,
                    test_start_date = NULL,
                    test_end_date = NULL
                """
            )
            reset_count = c.rowcount
            c.execute("SELECT COUNT(*) AS n FROM pentest_findings WHERE status IN ('open', 'draft')")
            remaining = c.fetchone()
            remaining_open = int(remaining["n"] if isinstance(remaining, dict) else remaining[0] or 0)
            conn.commit()

        stats = {
            "total_reset": reset_count,
            "remaining_open": remaining_open,
            "reports_deleted": 0,
            "report_delete_errors": 0,
            "generated_reports_deleted": 0,
            "generated_reports_delete_errors": 0,
        }
        return {
            "message": "Notebook fields reset. Findings and frozen reports were kept.",
            "stats": stats,
        }, 200
    except Exception as e:
        logger.error(f"Error resetting pentest notebooks: {e}")
        return {"error": "Failed to reset pentest progress."}, 500
