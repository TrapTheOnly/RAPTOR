import json
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

BIND_FILE_SOURCE_KEY = "bind_file"
BIND_AGENT_SOURCE_TYPE = "bind_agent"


def ensure_bind_file_source(db_path: str = DB_PATH) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT id FROM dns_sources WHERE key = ?", (BIND_FILE_SOURCE_KEY,))
        row = c.fetchone()
        if row:
            source_id = int(row["id"] if isinstance(row, dict) else row[0])
            conn.commit()
            return source_id
        c.execute(
            """
            INSERT INTO dns_sources (key, type, display_name, config, enabled)
            VALUES (?, 'bind_file', 'BIND zone files', '{}', 1)
            RETURNING id
            """,
            (BIND_FILE_SOURCE_KEY,),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def create_dns_source(
    *,
    key: str,
    source_type: str,
    display_name: str,
    config: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO dns_sources (key, type, display_name, config, enabled)
            VALUES (?, ?, ?, ?, 1)
            RETURNING id
            """,
            (key, source_type, display_name, json.dumps(config or {})),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def get_dns_source(source_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM dns_sources WHERE id = ?", (source_id,))
        row = c.fetchone()
    return dict(row) if row else None


def record_observations(
    source_id: int,
    records: List[Dict[str, Any]],
    batch_id: str,
    db_path: str = DB_PATH,
    cursor_value: Optional[str] = None,
) -> None:
    if not records:
        return
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        for record in records:
            fqdn = record.get("fqdn") or record.get("name")
            rrtype = str(record.get("rrtype") or "A").upper()
            rdata = record.get("rdata")
            if rdata is None:
                rdata = record.get("ip_address")
            ttl = record.get("ttl")
            c.execute(
                """
                INSERT INTO dns_observations (source_id, fqdn, rrtype, rdata, ttl, observed_at, batch_id)
                VALUES (?, ?, ?, ?, ?, NOW(), ?)
                """,
                (source_id, fqdn, rrtype, rdata, ttl, batch_id),
            )
        c.execute(
            """
            UPDATE dns_sources
            SET last_success_at = NOW(), last_error = NULL, cursor = ?
            WHERE id = ?
            """,
            (cursor_value or batch_id, source_id),
        )
        conn.commit()


def previously_observed_names(source_id: int, db_path: str = DB_PATH) -> List[str]:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT DISTINCT fqdn FROM dns_observations WHERE source_id = ? AND rrtype = 'A'",
            (source_id,),
        )
        rows = c.fetchall()
    names = []
    for row in rows:
        if isinstance(row, dict):
            names.append(str(row["fqdn"]))
        else:
            names.append(str(row[0]))
    return names


def mark_source_error(source_id: int, error: str, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE dns_sources SET last_error = ? WHERE id = ?",
            (error[:2000], source_id),
        )
        conn.commit()


__all__ = [
    "BIND_AGENT_SOURCE_TYPE",
    "BIND_FILE_SOURCE_KEY",
    "create_dns_source",
    "ensure_bind_file_source",
    "get_dns_source",
    "mark_source_error",
    "previously_observed_names",
    "record_observations",
]
