import json
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def create_notification(
    recipient: str,
    notification_type: str,
    title: str,
    message: str,
    actor: str = None,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH,
) -> int:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    metadata_json = json.dumps(metadata or {}, ensure_ascii=True)
    c.execute(
        """
        INSERT INTO notifications (recipient, type, title, message, actor, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (recipient, notification_type, title, message, actor, metadata_json, _now_iso()),
    )
    c.execute("SELECT lastval()")
    row = c.fetchone()
    notification_id = row[0] if row else 0
    conn.commit()
    conn.close()
    return notification_id


def create_notifications_bulk(
    notifications: List[Dict[str, Any]],
    db_path: str = DB_PATH,
) -> int:
    if not notifications:
        return 0
    conn = get_db_connection(db_path)
    c = conn.cursor()
    now = _now_iso()
    for n in notifications:
        metadata_json = json.dumps(n.get("metadata") or {}, ensure_ascii=True)
        c.execute(
            """
            INSERT INTO notifications (recipient, type, title, message, actor, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                n["recipient"],
                n["type"],
                n["title"],
                n["message"],
                n.get("actor"),
                metadata_json,
                now,
            ),
        )
    count = len(notifications)
    conn.commit()
    conn.close()
    return count


def get_notifications_for_user(
    username: str,
    limit: int = 50,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute(
        """
        SELECT id, recipient, type, title, message, actor, metadata, created_at
        FROM notifications
        WHERE recipient = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (username, limit),
    )
    rows = c.fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        raw_meta = item.get("metadata")
        if isinstance(raw_meta, str):
            try:
                item["metadata"] = json.loads(raw_meta)
            except (json.JSONDecodeError, TypeError):
                item["metadata"] = {}
        result.append(item)
    return result


def get_notification_count(username: str, db_path: str = DB_PATH) -> int:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM notifications WHERE recipient = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def delete_notification(
    notification_id: int,
    username: str,
    db_path: str = DB_PATH,
) -> bool:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        "DELETE FROM notifications WHERE id = ? AND recipient = ?",
        (notification_id, username),
    )
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def delete_all_notifications(username: str, db_path: str = DB_PATH) -> int:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE recipient = ?", (username,))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count
