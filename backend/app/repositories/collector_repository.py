import json
from typing import Any, Dict, List, Optional, Tuple

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection


def _row(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    payload = dict(row)
    zones = payload.get("last_zones") or "[]"
    if isinstance(zones, str):
        try:
            payload["last_zones"] = json.loads(zones)
        except json.JSONDecodeError:
            payload["last_zones"] = []
    return payload


def insert_enroll_token(
    *,
    token_hash: str,
    label: str,
    created_by: str,
    expires_at: str,
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO collector_enroll_tokens (token_hash, label, created_by, expires_at)
            VALUES (?, ?, ?, ?)
            RETURNING id
            """,
            (token_hash, label, created_by, expires_at),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def get_enroll_token_by_hash(token_hash: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, token_hash, label, created_by, created_at, expires_at, used_at, revoked_at
            FROM collector_enroll_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def mark_enroll_token_used(token_id: int, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE collector_enroll_tokens SET used_at = NOW() WHERE id = ? AND used_at IS NULL",
            (token_id,),
        )
        conn.commit()


def insert_agent(
    *,
    source_id: int,
    hostname: str,
    agent_version: str,
    token_hash: str,
    enroll_token_id: Optional[int],
    display_name: str = "",
    mode: str = "one_sided",
    callback_url: str = "",
    last_seen_ip: str = "",
    interval_seconds: int = 300,
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO collector_agents (
                source_id, hostname, display_name, agent_version, token_hash,
                enroll_token_id, last_seen_at, mode, callback_url, last_seen_ip,
                interval_seconds
            )
            VALUES (?, ?, ?, ?, ?, ?, NOW(), ?, ?, ?, ?)
            RETURNING id
            """,
            (
                source_id,
                hostname,
                display_name or hostname,
                agent_version,
                token_hash,
                enroll_token_id,
                mode,
                callback_url,
                last_seen_ip,
                interval_seconds,
            ),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def get_agent_by_token_hash(token_hash: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT a.*, s.key AS source_key, s.type AS source_type, s.enabled AS source_enabled
            FROM collector_agents a
            JOIN dns_sources s ON s.id = a.source_id
            WHERE a.token_hash = ?
            """,
            (token_hash,),
        )
        row = c.fetchone()
    return _row(row)


def get_agent_by_id(agent_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT a.*, s.key AS source_key, s.type AS source_type, s.enabled AS source_enabled,
                   s.last_success_at, s.last_error, s.cursor
            FROM collector_agents a
            JOIN dns_sources s ON s.id = a.source_id
            WHERE a.id = ?
            """,
            (agent_id,),
        )
        row = c.fetchone()
    return _row(row)


def list_agents(
    *,
    limit: int = 25,
    offset: int = 0,
    query: str = "",
    db_path: str = DB_PATH,
) -> Tuple[List[Dict[str, Any]], int]:
    like = f"%{query.strip().lower()}%"
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if query.strip():
            c.execute(
                """
                SELECT COUNT(*) AS n
                FROM collector_agents a
                WHERE LOWER(COALESCE(a.display_name, '')) LIKE ?
                   OR LOWER(a.hostname) LIKE ?
                """,
                (like, like),
            )
        else:
            c.execute("SELECT COUNT(*) AS n FROM collector_agents")
        count_row = c.fetchone()
        total = int(count_row["n"] if isinstance(count_row, dict) else count_row[0])
        if query.strip():
            c.execute(
                """
                SELECT a.*, s.key AS source_key, s.type AS source_type, s.enabled AS source_enabled,
                       s.last_success_at, s.last_error, s.cursor
                FROM collector_agents a
                JOIN dns_sources s ON s.id = a.source_id
                WHERE LOWER(COALESCE(a.display_name, '')) LIKE ?
                   OR LOWER(a.hostname) LIKE ?
                ORDER BY a.last_seen_at DESC NULLS LAST, a.id DESC
                LIMIT ? OFFSET ?
                """,
                (like, like, limit, offset),
            )
        else:
            c.execute(
                """
                SELECT a.*, s.key AS source_key, s.type AS source_type, s.enabled AS source_enabled,
                       s.last_success_at, s.last_error, s.cursor
                FROM collector_agents a
                JOIN dns_sources s ON s.id = a.source_id
                ORDER BY a.last_seen_at DESC NULLS LAST, a.id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        rows = c.fetchall()
    return [item for item in (_row(row) for row in rows) if item], total


def rotate_agent_token(agent_id: int, token_hash: str, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE collector_agents
            SET token_hash = ?, token_rotated_at = NOW(), last_seen_at = NOW()
            WHERE id = ? AND status = 'active'
            """,
            (token_hash, agent_id),
        )
        conn.commit()


def touch_agent_heartbeat(
    agent_id: int,
    *,
    agent_version: str,
    last_soa_serial: Optional[str],
    last_zones: List[Dict[str, Any]],
    mode: Optional[str] = None,
    callback_url: Optional[str] = None,
    last_seen_ip: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    ingest: bool = False,
    db_path: str = DB_PATH,
) -> None:
    assignments = [
        "last_seen_at = NOW()",
        "agent_version = ?",
        "last_soa_serial = ?",
        "last_zones = ?",
    ]
    params: List[Any] = [agent_version, last_soa_serial, json.dumps(last_zones)]
    if mode:
        assignments.append("mode = ?")
        params.append(mode)
    if callback_url is not None:
        assignments.append("callback_url = ?")
        params.append(callback_url)
    if last_seen_ip:
        assignments.append("last_seen_ip = ?")
        params.append(last_seen_ip)
    if interval_seconds is not None:
        assignments.append("interval_seconds = ?")
        params.append(interval_seconds)
    if ingest:
        assignments.append("last_ingest_at = NOW()")
    params.append(agent_id)
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            f"""
            UPDATE collector_agents
            SET {", ".join(assignments)}
            WHERE id = ? AND status = 'active'
            """,
            tuple(params),
        )
        conn.commit()


def update_agent_fields(
    agent_id: int,
    *,
    display_name: Optional[str] = None,
    callback_url: Optional[str] = None,
    db_path: str = DB_PATH,
) -> None:
    assignments = []
    params: List[Any] = []
    if display_name is not None:
        assignments.append("display_name = ?")
        params.append(display_name)
    if callback_url is not None:
        assignments.append("callback_url = ?")
        params.append(callback_url)
    if not assignments:
        return
    params.append(agent_id)
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            f"UPDATE collector_agents SET {', '.join(assignments)} WHERE id = ?",
            tuple(params),
        )
        if display_name is not None:
            c.execute(
                """
                UPDATE dns_sources
                SET display_name = ?
                WHERE id = (SELECT source_id FROM collector_agents WHERE id = ?)
                """,
                (display_name, agent_id),
            )
        conn.commit()


def mark_collect_requested(agent_id: Optional[int] = None, db_path: str = DB_PATH) -> int:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        if agent_id is None:
            c.execute(
                """
                UPDATE collector_agents
                SET collect_requested_at = NOW()
                WHERE status = 'active'
                """
            )
        else:
            c.execute(
                """
                UPDATE collector_agents
                SET collect_requested_at = NOW()
                WHERE id = ? AND status = 'active'
                """,
                (agent_id,),
            )
        updated = c.rowcount if c.rowcount is not None else 0
        conn.commit()
    return int(updated or 0)


def consume_collect_request(agent_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            UPDATE collector_agents
            SET collect_requested_at = NULL
            WHERE id = ? AND collect_requested_at IS NOT NULL
            RETURNING id
            """,
            (agent_id,),
        )
        row = c.fetchone()
        conn.commit()
    return row is not None


def list_active_agents(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT a.*, s.key AS source_key, s.type AS source_type, s.enabled AS source_enabled
            FROM collector_agents a
            JOIN dns_sources s ON s.id = a.source_id
            WHERE a.status = 'active'
            ORDER BY a.id
            """
        )
        rows = c.fetchall()
    return [item for item in (_row(row) for row in rows) if item]


def revoke_agent(agent_id: int, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE collector_agents
            SET status = 'revoked', token_hash = token_hash || ':revoked:' || id::text
            WHERE id = ? AND status = 'active'
            """,
            (agent_id,),
        )
        c.execute(
            "UPDATE dns_sources SET enabled = 0 WHERE id = (SELECT source_id FROM collector_agents WHERE id = ?)",
            (agent_id,),
        )
        conn.commit()


def delete_agent(agent_id: int, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE dns_sources SET enabled = 0 WHERE id = (SELECT source_id FROM collector_agents WHERE id = ?)",
            (agent_id,),
        )
        c.execute("DELETE FROM collector_agents WHERE id = ?", (agent_id,))
        conn.commit()
