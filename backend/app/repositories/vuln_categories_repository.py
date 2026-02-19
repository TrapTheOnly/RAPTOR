import sqlite3
from typing import Any, Dict, List, Optional

from app.config import DB_PATH


def fetch_vuln_categories(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, created_by, created_at, is_custom FROM vuln_categories ORDER BY name ASC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_vuln_category(name: str, created_by: str, db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO vuln_categories (name, created_by, created_at, is_custom)
        VALUES (?, ?, datetime('now', '+4 hours'), 1)
        """,
        (name, created_by),
    )
    category_id = c.lastrowid
    conn.commit()
    conn.close()
    return category_id


def delete_vuln_category(category_id: int, db_path: str = DB_PATH) -> bool:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM vuln_categories WHERE id = ?", (category_id,))
    deleted = c.rowcount > 0
    if deleted:
        conn.commit()
    conn.close()
    return deleted
