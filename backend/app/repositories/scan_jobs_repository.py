import json
import logging
from typing import Any, Dict, List, Optional

from app.integrations.db.connection import ROW_AS_DICT, get_db_connection, get_table_columns

logger = logging.getLogger(__name__)


_JOB_STATUSES = {"running", "naming", "pending", "queued", "failed", "completed"}


def create_scan_job(
    application_id: int,
    wave_id: int,
    record_ids: List[int],
    launched_by: str,
    provider_type: str = "",
    model_id: str = "",
    title: str = "",
    status: str = "running",
) -> Dict[str, Any]:
    job_status = str(status or "running")
    if job_status not in _JOB_STATUSES:
        job_status = "running"
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        columns = get_table_columns(c, "scan_jobs")
        if "title" in columns:
            c.execute(
                """
                INSERT INTO scan_jobs (
                    application_id, wave_id, status, record_ids, launched_by,
                    provider_type, model_id, title
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING *
                """,
                (
                    int(application_id),
                    int(wave_id),
                    job_status,
                    json.dumps([int(item) for item in record_ids]),
                    launched_by or "",
                    provider_type or "",
                    model_id or "",
                    str(title or ""),
                ),
            )
        else:
            c.execute(
                """
                INSERT INTO scan_jobs (
                    application_id, wave_id, status, record_ids, launched_by,
                    provider_type, model_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING *
                """,
                (
                    int(application_id),
                    int(wave_id),
                    job_status,
                    json.dumps([int(item) for item in record_ids]),
                    launched_by or "",
                    provider_type or "",
                    model_id or "",
                ),
            )
        row = c.fetchone()
        conn.commit()
    return _hydrate(row)


def get_scan_job(job_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM scan_jobs WHERE id = ?", (int(job_id),))
        row = c.fetchone()
    return _hydrate(row) if row else None


def latest_job_for_wave(wave_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT * FROM scan_jobs
            WHERE wave_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(wave_id),),
        )
        row = c.fetchone()
    return _hydrate(row) if row else None


def running_job_for_wave(wave_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT * FROM scan_jobs
            WHERE wave_id = ? AND status IN ('running', 'naming', 'pending', 'queued')
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(wave_id),),
        )
        row = c.fetchone()
    return _hydrate(row) if row else None


def list_running_scan_jobs() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM scan_jobs WHERE status = 'running' ORDER BY id ASC")
        rows = c.fetchall()
    return [_hydrate(row) for row in rows or []]


def count_running_scan_jobs() -> int:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) AS cnt FROM scan_jobs WHERE status IN ('running', 'naming', 'pending', 'queued')"
        )
        row = c.fetchone()
    if row is None:
        return 0
    return int(row[0] if not isinstance(row, dict) else row["cnt"])


def list_jobs_for_wave(wave_id: int) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT * FROM scan_jobs
            WHERE wave_id = ?
            ORDER BY id DESC
            """,
            (int(wave_id),),
        )
        rows = c.fetchall() or []
    return [_hydrate(row) for row in rows]


def update_scan_job(job_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {"status", "last_error", "title"}
    updates = {k: v for k, v in (fields or {}).items() if k in allowed}
    if not updates:
        return get_scan_job(job_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [int(job_id)]
    with get_db_connection() as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(f"UPDATE scan_jobs SET {set_clause} WHERE id = ? RETURNING *", values)
        row = c.fetchone()
        conn.commit()
    return _hydrate(row) if row else None


def _hydrate(row: Any) -> Dict[str, Any]:
    item = dict(row or {})
    raw_ids = item.get("record_ids")
    if isinstance(raw_ids, str):
        try:
            raw_ids = json.loads(raw_ids)
        except (json.JSONDecodeError, TypeError):
            raw_ids = []
    if not isinstance(raw_ids, list):
        raw_ids = []
    item["record_ids"] = [int(value) for value in raw_ids if str(value).isdigit() or isinstance(value, int)]
    launched_at = item.get("launched_at")
    if hasattr(launched_at, "isoformat"):
        item["launched_at"] = launched_at.isoformat()
    return item


def scan_jobs_table_ready() -> bool:
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            return "id" in get_table_columns(c, "scan_jobs")
    except Exception:
        logger.debug("scan_jobs table not ready", exc_info=True)
        return False


__all__ = [
    "count_running_scan_jobs",
    "create_scan_job",
    "list_jobs_for_wave",
    "list_running_scan_jobs",
    "get_scan_job",
    "latest_job_for_wave",
    "running_job_for_wave",
    "scan_jobs_table_ready",
    "update_scan_job",
]
