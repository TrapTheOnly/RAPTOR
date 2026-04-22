import json
import logging
from typing import Any, Dict, List, Optional

from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

logger = logging.getLogger(__name__)

VALID_EVENT_TYPES = {
    "api_call",
    "tool_call",
    "tool_result",
    "finding",
    "status",
}


def insert_scan_event(record_id: int, event_type: str, payload: Dict[str, Any]) -> Optional[int]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO scan_events (record_id, event_type, payload) VALUES (?, ?, ?) RETURNING id",
            (record_id, event_type, json.dumps(payload)),
        )
        row = c.fetchone()
        if row:
            return int(row[0]) if not isinstance(row, dict) else int(row["id"])
    return None


def fetch_scan_events_after(record_id: int, after_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, record_id, event_type, payload, ts
            FROM scan_events
            WHERE record_id = ? AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (record_id, after_id, limit),
        )
        rows = c.fetchall()
    result = []
    for row in rows:
        item = dict(row)
        raw_payload = item.get("payload")
        if isinstance(raw_payload, str):
            try:
                item["payload"] = json.loads(raw_payload)
            except (json.JSONDecodeError, TypeError):
                item["payload"] = {}
        ts = item.get("ts")
        item["ts"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
        result.append(item)
    return result


def delete_scan_events_for_record(record_id: int) -> int:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM scan_events WHERE record_id = ?", (record_id,))
        count = c.rowcount
    return count


__all__ = [
    "VALID_EVENT_TYPES",
    "delete_scan_events_for_record",
    "fetch_scan_events_after",
    "insert_scan_event",
]
