from datetime import UTC, datetime
from typing import Any, Dict, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def get_email_config(db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute(
        """
        SELECT id, smtp_host, smtp_port, smtp_user, smtp_password,
               smtp_use_tls, sender_email, sender_name, enabled,
               updated_by, updated_at
        FROM email_config
        LIMIT 1
        """
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_email_config(config: Dict[str, Any], db_path: str = DB_PATH) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("SELECT id FROM email_config LIMIT 1")
    existing = c.fetchone()

    if existing:
        row_id = existing[0] if not isinstance(existing, dict) else existing["id"]
        c.execute(
            """
            UPDATE email_config
            SET smtp_host = ?, smtp_port = ?, smtp_user = ?, smtp_password = ?,
                smtp_use_tls = ?, sender_email = ?, sender_name = ?,
                enabled = ?, updated_by = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                config["smtp_host"],
                config["smtp_port"],
                config.get("smtp_user", ""),
                config.get("smtp_password", ""),
                1 if config.get("smtp_use_tls", True) else 0,
                config["sender_email"],
                config.get("sender_name", "RAPTOR"),
                1 if config.get("enabled", False) else 0,
                config.get("updated_by", ""),
                _now_iso(),
                row_id,
            ),
        )
    else:
        c.execute(
            """
            INSERT INTO email_config
                (smtp_host, smtp_port, smtp_user, smtp_password,
                 smtp_use_tls, sender_email, sender_name,
                 enabled, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config["smtp_host"],
                config["smtp_port"],
                config.get("smtp_user", ""),
                config.get("smtp_password", ""),
                1 if config.get("smtp_use_tls", True) else 0,
                config["sender_email"],
                config.get("sender_name", "RAPTOR"),
                1 if config.get("enabled", False) else 0,
                config.get("updated_by", ""),
                _now_iso(),
            ),
        )
    conn.commit()
    conn.close()
