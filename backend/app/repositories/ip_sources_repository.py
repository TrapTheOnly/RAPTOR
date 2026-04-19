from typing import Any, Dict, List, Optional, Tuple

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection


def fetch_ip_sources(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute("SELECT id, source_name, ip_address FROM ip_sources")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_ip_source(source_name: str, ip_address: str, db_path: str = DB_PATH) -> int:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO ip_sources (source_name, ip_address)
        VALUES (?, ?)
        """,
        (source_name, ip_address),
    )
    conn.commit()

    c.execute(
        """
        UPDATE records
        SET source = ?,
            status = 'updated',
            last_modification_date = (NOW() + INTERVAL '4 hours')
        WHERE ip_address = ?
        """,
        (source_name, ip_address),
    )
    updated_count = c.rowcount

    conn.commit()
    conn.close()
    return updated_count


def delete_ip_source(ip_address: str, db_path: str = DB_PATH) -> Optional[Tuple[str, int]]:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    c.execute("SELECT source_name FROM ip_sources WHERE ip_address = ?", (ip_address,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None

    source_name = row[0]
    c.execute("DELETE FROM ip_sources WHERE ip_address = ?", (ip_address,))
    conn.commit()

    c.execute(
        """
        UPDATE records
        SET source = 'Other',
            status = 'updated',
            last_modification_date = (NOW() + INTERVAL '4 hours')
        WHERE ip_address = ?
        """,
        (ip_address,),
    )
    updated_count = c.rowcount
    conn.commit()
    conn.close()

    return source_name, updated_count
