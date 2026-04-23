import logging
from typing import Any, Dict, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

logger = logging.getLogger(__name__)


def get_scanner_config(db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM scanner_config ORDER BY id ASC LIMIT 1")
        row = c.fetchone()
    return dict(row) if row else None


def update_scanner_config(fields: Dict[str, Any], db_path: str = DB_PATH) -> bool:
    allowed = {
        "aws_region", "bedrock_model_id", "cost_limit_usd",
        "input_cost_per_1m", "output_cost_per_1m",
        "max_concurrent_scans", "enabled",
        "proxy_url", "proxy_username", "proxy_password",
        "updated_by", "updated_at",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        c.execute(f"UPDATE scanner_config SET {set_clause}", list(updates.values()))
        conn.commit()
    return True


def count_running_scans(db_path: str = DB_PATH) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS cnt FROM pentest_data WHERE scan_status = 'running'")
        row = c.fetchone()
    if not row:
        return 0
    return int(row["cnt"] if isinstance(row, dict) else row[0])


__all__ = [
    "count_running_scans",
    "get_scanner_config",
    "update_scanner_config",
]
