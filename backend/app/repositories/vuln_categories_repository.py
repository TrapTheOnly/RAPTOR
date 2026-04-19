from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection


def fetch_vuln_categories(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute("SELECT id, name, created_by, created_at, is_custom FROM vuln_categories ORDER BY name ASC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_vuln_category(name: str, created_by: str, db_path: str = DB_PATH) -> int:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO vuln_categories (name, created_by, created_at, is_custom)
        VALUES (?, ?, (NOW() + INTERVAL '4 hours'), 1)
        RETURNING id
        """,
        (name, created_by),
    )
    inserted = c.fetchone()
    category_id = inserted[0] if inserted else None
    conn.commit()
    conn.close()
    if category_id is None:
        raise RuntimeError("Failed to create vulnerability category.")
    return category_id


def delete_vuln_category(category_id: int, db_path: str = DB_PATH) -> bool:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM vuln_categories WHERE id = ?", (category_id,))
    deleted = c.rowcount > 0
    if deleted:
        conn.commit()
    conn.close()
    return deleted
