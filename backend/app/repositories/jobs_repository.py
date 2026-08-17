import json
from typing import Any, Dict, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection


def enqueue_job(kind: str, payload: Optional[Dict[str, Any]] = None, db_path: str = DB_PATH) -> int:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO app_jobs (kind, payload, status, run_after, attempts)
            VALUES (?, ?, 'pending', NOW(), 0)
            RETURNING id
            """,
            (kind, json.dumps(payload or {})),
        )
        row = c.fetchone()
        conn.commit()
    return int(row[0] if not isinstance(row, dict) else row["id"])


def has_pending_or_running(kind: str, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT 1 FROM app_jobs
            WHERE kind = ? AND status IN ('pending', 'running')
            LIMIT 1
            """,
            (kind,),
        )
        return c.fetchone() is not None


def claim_next_job(db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            UPDATE app_jobs
            SET status = 'running', locked_at = NOW(), attempts = attempts + 1
            WHERE id = (
                SELECT id FROM app_jobs
                WHERE status = 'pending' AND run_after <= NOW()
                ORDER BY id ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, kind, payload, attempts
            """
        )
        row = c.fetchone()
        conn.commit()
    return dict(row) if row else None


def complete_job(job_id: int, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE app_jobs
            SET status = 'completed', locked_at = NULL, last_error = NULL
            WHERE id = ?
            """,
            (job_id,),
        )
        conn.commit()


def fail_job(job_id: int, error: str, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE app_jobs
            SET status = 'failed', locked_at = NULL, last_error = ?
            WHERE id = ?
            """,
            (error[:2000], job_id),
        )
        conn.commit()


__all__ = [
    "claim_next_job",
    "complete_job",
    "enqueue_job",
    "fail_job",
    "has_pending_or_running",
]
