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


def insert_scan_event(
    record_id: int,
    event_type: str,
    payload: Dict[str, Any],
    job_id: Optional[int] = None,
) -> Optional[int]:
    with get_db_connection() as conn:
        c = conn.cursor()
        columns = None
        try:
            from app.integrations.db.connection import get_table_columns

            columns = get_table_columns(c, "scan_events")
        except Exception:
            columns = None
        if job_id and columns and "job_id" in columns:
            c.execute(
                """
                INSERT INTO scan_events (record_id, event_type, payload, job_id)
                VALUES (?, ?, ?, ?) RETURNING id
                """,
                (record_id, event_type, json.dumps(payload), int(job_id)),
            )
        else:
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


def fetch_scan_events_after_wave(wave_id: int, after_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    from app.repositories.scan_jobs_repository import latest_job_for_wave, scan_jobs_table_ready

    record_ids: List[int] = []
    job_id = None
    if scan_jobs_table_ready():
        job = latest_job_for_wave(wave_id)
        if job:
            job_id = int(job["id"])
            record_ids = [int(item) for item in (job.get("record_ids") or [])]
    if not record_ids:
        from app.repositories.phase2b_repository import get_wave, list_live_wave_hosts

        wave = get_wave(wave_id)
        if wave:
            record_ids = [
                int(host["id"])
                for host in list_live_wave_hosts(wave)
                if host.get("in_scope") is not False
            ]
    if not record_ids:
        return []
    placeholders = ",".join("?" for _ in record_ids)
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        try:
            from app.integrations.db.connection import get_table_columns

            columns = get_table_columns(c, "scan_events")
        except Exception:
            columns = set()
        select_job = ", e.job_id" if columns and "job_id" in columns else ""
        job_clause = " OR e.job_id = ?" if job_id and select_job else ""
        params: list = [after_id, *record_ids]
        if job_id and select_job:
            params.append(int(job_id))
        params.append(limit)
        c.execute(
            f"""
            SELECT e.id, e.record_id, e.event_type, e.payload, e.ts{select_job}
            FROM scan_events e
            WHERE e.id > ?
              AND (e.record_id IN ({placeholders}){job_clause})
            ORDER BY e.id ASC
            LIMIT ?
            """,
            params,
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


def delete_scan_events_for_records(record_ids: List[int]) -> int:
    ids = [int(item) for item in record_ids or [] if item]
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(f"DELETE FROM scan_events WHERE record_id IN ({placeholders})", ids)
        count = c.rowcount
    return count


__all__ = [
    "VALID_EVENT_TYPES",
    "delete_scan_events_for_record",
    "delete_scan_events_for_records",
    "fetch_scan_events_after",
    "fetch_scan_events_after_wave",
    "insert_scan_event",
]
