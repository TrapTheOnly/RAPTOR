from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config import DB_PATH
from app.integrations.db.connection import get_db_connection


def _as_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return None


def upsert_session_tokens(
    session_key: str,
    username: str,
    access_token: str,
    refresh_token: str,
    access_expires_at: datetime,
    db_path: str = DB_PATH,
) -> None:
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sso_session_tokens (
                session_key, username, access_token, refresh_token, access_expires_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, NOW())
            ON CONFLICT (session_key) DO UPDATE SET
                username = EXCLUDED.username,
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                access_expires_at = EXCLUDED.access_expires_at,
                updated_at = NOW()
            """,
            (session_key, username, access_token, refresh_token or "", access_expires_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_session_tokens(session_key: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_key, username, access_token, refresh_token, access_expires_at
            FROM sso_session_tokens
            WHERE session_key = ?
            """,
            (session_key,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    if isinstance(row, dict):
        payload = dict(row)
    else:
        payload = {
            "session_key": row[0],
            "username": row[1],
            "access_token": row[2],
            "refresh_token": row[3],
            "access_expires_at": row[4],
        }
    payload["access_expires_at"] = _as_utc(payload.get("access_expires_at"))
    return payload


def delete_session_tokens(session_key: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    existing = get_session_tokens(session_key, db_path=db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sso_session_tokens WHERE session_key = ?", (session_key,))
        conn.commit()
    finally:
        conn.close()
    return existing


__all__ = ["delete_session_tokens", "get_session_tokens", "upsert_session_tokens"]
