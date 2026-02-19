import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from app.config import DB_PATH


def fetch_applications(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT id, name, created_by, created_at
            FROM applications
            ORDER BY name
            """
        )
        rows = c.fetchall()
    return [dict(ix) for ix in rows]


def create_application(name: str, created_by: str, db_path: str = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO applications (name, created_by, created_at)
            VALUES (?, ?, datetime('now', '+4 hours'))
            """,
            (name, created_by),
        )
        conn.commit()


def update_application(app_id: int, name: str, db_path: str = DB_PATH) -> bool:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, name FROM applications WHERE id = ?", (app_id,))
        existing_app = c.fetchone()
        if not existing_app:
            return False

        old_name = str(existing_app["name"] or "").strip()
        c.execute("UPDATE applications SET name = ? WHERE id = ?", (name, app_id))

        c.execute("PRAGMA table_info(records)")
        record_columns = {row["name"] for row in c.fetchall()}
        if "application_name" in record_columns:
            c.execute(
                """
                UPDATE records
                SET application_id = ?
                WHERE (application_id IS NULL OR application_id = 0)
                  AND application_name = ?
                """,
                (app_id, old_name),
            )
            c.execute(
                """
                UPDATE records
                SET application_name = ?
                WHERE application_id = ?
                   OR application_name = ?
                """,
                (name, app_id, old_name),
            )

        conn.commit()
    return True


def delete_application(app_id: int, db_path: str = DB_PATH) -> bool:
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM applications WHERE id = ?", (app_id,))
        if not c.fetchone():
            return False

        c.execute("UPDATE records SET application_id = NULL WHERE application_id = ?", (app_id,))
        c.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        conn.commit()
    return True
