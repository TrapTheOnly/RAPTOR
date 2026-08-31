import json
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.domain.burp.fields import as_json
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection


def _row(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    payload = dict(row)
    for key in (
        "excerpt_json",
        "placeholder_map",
        "extract_rule",
        "payload_json",
        "result_json",
    ):
        if key in payload:
            payload[key] = as_json(payload.get(key), {})
    return payload


def insert_enroll_token(
    *,
    wave_id: int,
    application_id: int,
    token_hash: str,
    created_by: str,
    expires_at: str,
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO burp_enroll_tokens
                (wave_id, application_id, token_hash, created_by, expires_at)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            (wave_id, application_id, token_hash, created_by, expires_at),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def revoke_wave_enroll_tokens(wave_id: int, db_path: str = DB_PATH) -> int:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE burp_enroll_tokens
            SET revoked_at = NOW()
            WHERE wave_id = ? AND revoked_at IS NULL
            """,
            (wave_id,),
        )
        updated = c.rowcount or 0
        conn.commit()
    return int(updated)


def get_enroll_token_by_hash(token_hash: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, wave_id, application_id, token_hash, created_by, created_at,
                   expires_at, used_at, revoked_at
            FROM burp_enroll_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def latest_enroll_token(wave_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, wave_id, application_id, created_by, created_at, expires_at, used_at, revoked_at
            FROM burp_enroll_tokens
            WHERE wave_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (wave_id,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def mark_enroll_token_used(token_id: int, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE burp_enroll_tokens SET used_at = NOW() WHERE id = ? AND used_at IS NULL",
            (token_id,),
        )
        conn.commit()


def insert_agent(
    *,
    wave_id: int,
    application_id: int,
    enroll_token_id: Optional[int],
    username: str,
    hostname: str,
    burp_version: str,
    token_hash: str,
    last_seen_ip: str = "",
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO burp_agents (
                wave_id, application_id, enroll_token_id, username, hostname,
                burp_version, token_hash, last_seen_ip, last_heartbeat_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NOW())
            RETURNING id
            """,
            (
                wave_id,
                application_id,
                enroll_token_id,
                username,
                hostname,
                burp_version,
                token_hash,
                last_seen_ip,
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
            SELECT id, wave_id, application_id, enroll_token_id, username, hostname,
                   burp_version, token_hash, token_rotated_at, status, last_seen_ip,
                   last_heartbeat_at, started_at, enrolled_at
            FROM burp_agents
            WHERE token_hash = ?
            """,
            (token_hash,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def get_agent(agent_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, wave_id, application_id, enroll_token_id, username, hostname,
                   burp_version, token_hash, token_rotated_at, status, last_seen_ip,
                   last_heartbeat_at, started_at, enrolled_at
            FROM burp_agents
            WHERE id = ?
            """,
            (agent_id,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def latest_agent_for_wave(wave_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, wave_id, application_id, username, hostname, burp_version, status,
                   last_seen_ip, last_heartbeat_at, started_at, enrolled_at
            FROM burp_agents
            WHERE wave_id = ?
            ORDER BY last_heartbeat_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (wave_id,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def list_agents_for_wave(wave_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, wave_id, username, hostname, burp_version, status,
                   last_heartbeat_at, started_at
            FROM burp_agents
            WHERE wave_id = ?
            ORDER BY last_heartbeat_at DESC NULLS LAST, id DESC
            """,
            (wave_id,),
        )
        return [dict(row) for row in c.fetchall() or []]


def touch_agent_heartbeat(
    agent_id: int,
    *,
    burp_version: str = "",
    last_seen_ip: str = "",
    db_path: str = DB_PATH,
) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE burp_agents
            SET last_heartbeat_at = NOW(),
                burp_version = CASE WHEN ? = '' THEN burp_version ELSE ? END,
                last_seen_ip = CASE WHEN ? = '' THEN last_seen_ip ELSE ? END
            WHERE id = ?
            """,
            (burp_version, burp_version, last_seen_ip, last_seen_ip, agent_id),
        )
        conn.commit()


def rotate_agent_token(agent_id: int, token_hash: str, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE burp_agents
            SET token_hash = ?, token_rotated_at = NOW(), last_heartbeat_at = NOW()
            WHERE id = ?
            """,
            (token_hash, agent_id),
        )
        conn.commit()


def revoke_wave_agents(wave_id: int, db_path: str = DB_PATH) -> int:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE burp_agents
            SET status = 'revoked',
                token_hash = token_hash || ':revoked:' || id::text
            WHERE wave_id = ? AND status = 'active'
            """,
            (wave_id,),
        )
        updated = c.rowcount or 0
        conn.commit()
    return int(updated)


def upsert_event(
    *,
    wave_id: int,
    application_id: int,
    agent_id: Optional[int],
    tool: str,
    dedupe_key: str,
    host: str,
    path: str,
    method: str,
    status: Optional[int],
    excerpt_json: Dict[str, Any],
    scanner_type: str = "",
    scanner_name: str = "",
    scanner_severity: str = "",
    scanner_confidence: str = "",
    scanner_parameter: str = "",
    scanner_detail: str = "",
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    excerpt = json.dumps(excerpt_json or {})
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO burp_events (
                wave_id, application_id, agent_id, tool, dedupe_key, host, path, method,
                status, count, excerpt_json, scanner_type, scanner_name, scanner_severity,
                scanner_confidence, scanner_parameter, scanner_detail
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (wave_id, dedupe_key) DO UPDATE SET
                count = burp_events.count + 1,
                last_seen_at = NOW(),
                status = COALESCE(EXCLUDED.status, burp_events.status),
                excerpt_json = EXCLUDED.excerpt_json,
                agent_id = COALESCE(EXCLUDED.agent_id, burp_events.agent_id)
            RETURNING id, wave_id, tool, dedupe_key, host, path, method, status, count,
                      last_seen_at, excerpt_json, scanner_name, scanner_severity
            """,
            (
                wave_id,
                application_id,
                agent_id,
                tool,
                dedupe_key,
                host,
                path,
                method,
                status,
                excerpt,
                scanner_type,
                scanner_name,
                scanner_severity,
                scanner_confidence,
                scanner_parameter,
                scanner_detail,
            ),
        )
        row = c.fetchone()
        conn.commit()
    return _row(row) or {}


def list_events_for_wave(wave_id: int, limit: int = 500, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, wave_id, tool, host, path, method, status, count, last_seen_at,
                   excerpt_json, scanner_type, scanner_name, scanner_severity,
                   scanner_confidence, scanner_parameter, scanner_detail
            FROM burp_events
            WHERE wave_id = ?
            ORDER BY last_seen_at DESC, id DESC
            LIMIT ?
            """,
            (wave_id, limit),
        )
        return [_row(row) or {} for row in c.fetchall() or []]


def get_event(event_id: int, wave_id: Optional[int] = None, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if wave_id is None:
            c.execute("SELECT * FROM burp_events WHERE id = ?", (event_id,))
        else:
            c.execute("SELECT * FROM burp_events WHERE id = ? AND wave_id = ?", (event_id, wave_id))
        row = c.fetchone()
    return _row(row)


def search_events(
    wave_id: int,
    *,
    path_prefix: str = "",
    issue_name: str = "",
    limit: int = 5,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    clauses = ["wave_id = ?"]
    params: List[Any] = [wave_id]
    if path_prefix:
        clauses.append("path LIKE ?")
        params.append(str(path_prefix) + "%")
    if issue_name:
        clauses.append("scanner_name ILIKE ?")
        params.append("%" + issue_name + "%")
    params.append(max(1, min(int(limit), 20)))
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            f"""
            SELECT id, tool, host, path, method, status, count, scanner_name, scanner_severity
            FROM burp_events
            WHERE {' AND '.join(clauses)}
            ORDER BY last_seen_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [dict(row) for row in c.fetchall() or []]


def latest_http_event(
    wave_id: int,
    host: str,
    path: str = "",
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    """Newest Repeater/Intruder event for this host (path when it matches)."""
    from app.domain.burp.fields import normalize_host, normalize_path

    target_host = normalize_host(host)
    target_path = normalize_path(path) if path else ""
    if not target_host:
        return None
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT *
            FROM burp_events
            WHERE wave_id = ?
              AND host = ?
              AND tool IN ('repeater', 'intruder')
            ORDER BY
              CASE WHEN path = ? THEN 0 ELSE 1 END,
              CASE tool WHEN 'repeater' THEN 0 ELSE 1 END,
              last_seen_at DESC,
              id DESC
            LIMIT 1
            """,
            (int(wave_id), target_host, target_path or "/"),
        )
        row = c.fetchone()
    return _row(row)


def count_events(wave_id: int, db_path: str = DB_PATH) -> int:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM burp_events WHERE wave_id = ?", (wave_id,))
        row = c.fetchone()
    if not row:
        return 0
    if isinstance(row, dict):
        return int(next(iter(row.values())))
    return int(row[0])


def upsert_auth_template(
    *,
    wave_id: int,
    application_id: int,
    agent_id: Optional[int],
    host: str,
    method: str,
    path: str,
    request_ciphertext: str,
    placeholder_map: Dict[str, Any],
    extract_rule: Dict[str, Any],
    created_by: str,
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO burp_auth_templates (
                wave_id, application_id, agent_id, host, method, path,
                request_ciphertext, placeholder_map, extract_rule, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (wave_id, host) DO UPDATE SET
                method = EXCLUDED.method,
                path = EXCLUDED.path,
                request_ciphertext = EXCLUDED.request_ciphertext,
                placeholder_map = EXCLUDED.placeholder_map,
                extract_rule = EXCLUDED.extract_rule,
                agent_id = COALESCE(EXCLUDED.agent_id, burp_auth_templates.agent_id),
                updated_at = NOW()
            RETURNING id
            """,
            (
                wave_id,
                application_id,
                agent_id,
                host,
                method,
                path,
                request_ciphertext,
                json.dumps(placeholder_map or {}),
                json.dumps(extract_rule or {}),
                created_by,
            ),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def get_auth_template(wave_id: int, host: str = "", db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if host:
            c.execute(
                "SELECT * FROM burp_auth_templates WHERE wave_id = ? AND host = ?",
                (wave_id, host),
            )
        else:
            c.execute(
                """
                SELECT * FROM burp_auth_templates
                WHERE wave_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (wave_id,),
            )
        row = c.fetchone()
    return _row(row)


def insert_job(
    *,
    wave_id: int,
    application_id: int,
    agent_id: Optional[int],
    kind: str,
    host: str,
    path: str,
    payload_json: Dict[str, Any],
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO burp_jobs (
                wave_id, application_id, agent_id, kind, host, path, payload_json, title
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (wave_id, application_id, agent_id, kind, host, path, json.dumps(payload_json or {}), ""),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def get_job(job_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM burp_jobs WHERE id = ?", (job_id,))
        row = c.fetchone()
    return _row(row)


def update_job(
    job_id: int,
    *,
    status: Optional[str] = None,
    title: Optional[str] = None,
    result_json: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    db_path: str = DB_PATH,
) -> None:
    assignments = ["updated_at = NOW()"]
    values: List[Any] = []
    if status is not None:
        assignments.append("status = ?")
        values.append(status)
    if title is not None:
        assignments.append("title = ?")
        values.append(title)
    if result_json is not None:
        assignments.append("result_json = ?")
        values.append(json.dumps(result_json))
    if error is not None:
        assignments.append("error = ?")
        values.append(error)
    if len(assignments) == 1:
        return
    values.append(job_id)
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            f"UPDATE burp_jobs SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        conn.commit()


def list_jobs_for_wave(wave_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT * FROM burp_jobs
            WHERE wave_id = ?
            ORDER BY id DESC
            """,
            (int(wave_id),),
        )
        rows = c.fetchall() or []
    return [_row(row) or {} for row in rows]


def get_proposal(proposal_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM burp_proposals WHERE id = ?", (int(proposal_id),))
        row = c.fetchone()
    return _row(row)


def list_proposals_for_wave(
    wave_id: int,
    *,
    kind: str = "",
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    clauses = ["wave_id = ?"]
    params: List[Any] = [int(wave_id)]
    if kind:
        clauses.append("kind = ?")
        params.append(str(kind))
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            f"""
            SELECT * FROM burp_proposals
            WHERE {" AND ".join(clauses)}
            ORDER BY id DESC
            """,
            tuple(params),
        )
        rows = c.fetchall() or []
    return [_row(row) or {} for row in rows]


def get_proposal_for_job(job_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT * FROM burp_proposals
            WHERE job_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(job_id),),
        )
        row = c.fetchone()
    return _row(row)


def get_proposal_for_finding(finding_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    wanted = str(finding_id or "").strip()
    if not wanted:
        return None
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT * FROM burp_proposals
            WHERE finding_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (wanted,),
        )
        row = c.fetchone()
    return _row(row)


def update_proposal(
    proposal_id: int,
    *,
    status: Optional[str] = None,
    finding_id: Optional[str] = None,
    db_path: str = DB_PATH,
) -> None:
    assignments = []
    values: List[Any] = []
    if status is not None:
        assignments.append("status = ?")
        values.append(status)
    if finding_id is not None:
        assignments.append("finding_id = ?")
        values.append(finding_id)
        assignments.append("accepted_at = NOW()")
    if not assignments:
        return
    values.append(int(proposal_id))
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            f"UPDATE burp_proposals SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        conn.commit()


def unlink_proposals_for_finding(finding_id: str, db_path: str = DB_PATH) -> None:
    wanted = str(finding_id or "").strip()
    if not wanted:
        return
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE burp_proposals
            SET finding_id = '', status = 'pending', accepted_at = NULL
            WHERE finding_id = ?
            """,
            (wanted,),
        )
        conn.commit()


def insert_proposal(
    *,
    wave_id: int,
    application_id: int,
    job_id: Optional[int],
    kind: str,
    title: str,
    description: str,
    result_json: Dict[str, Any],
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO burp_proposals (
                wave_id, application_id, job_id, kind, title, description, result_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                wave_id,
                application_id,
                job_id,
                kind,
                title,
                description,
                json.dumps(result_json or {}),
            ),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])
