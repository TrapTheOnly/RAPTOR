import json
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection, get_table_columns


def _table_exists(cursor, name: str) -> bool:
    try:
        return bool(get_table_columns(cursor, name))
    except Exception:
        return False


def wave_env_ids(wave: Dict[str, Any]) -> List[int]:
    ids = []
    seen = set()
    for item in list(wave.get("env_ids") or []):
        try:
            env_id = int(item)
        except (TypeError, ValueError):
            continue
        if env_id in seen:
            continue
        seen.add(env_id)
        ids.append(env_id)
    raw = wave.get("environment_id")
    if raw not in (None, ""):
        try:
            env_id = int(raw)
        except (TypeError, ValueError):
            env_id = None
        if env_id is not None and env_id not in seen:
            ids.append(env_id)
    return ids


def _hydrate_wave(row: Dict[str, Any], members: Optional[List[str]] = None) -> Dict[str, Any]:
    item = dict(row)
    raw_ids = item.get("env_ids") or "[]"
    item["env_ids"] = raw_ids if isinstance(raw_ids, list) else json.loads(raw_ids or "[]")
    raw_snapshot = item.get("host_snapshot") or "[]"
    item["host_snapshot"] = raw_snapshot if isinstance(raw_snapshot, list) else json.loads(raw_snapshot or "[]")
    if item.get("environment_id") in (None, "") and item["env_ids"]:
        try:
            item["environment_id"] = int(item["env_ids"][0])
        except (TypeError, ValueError, IndexError):
            item["environment_id"] = None
    if members is not None:
        item["members"] = members
    item["started"] = bool(item.get("started_at"))
    return item


def _list_wave_members(cursor, wave_id: int) -> List[str]:
    if not _table_exists(cursor, "engagement_wave_members"):
        return []
    cursor.execute(
        "SELECT username FROM engagement_wave_members WHERE wave_id = ? ORDER BY username",
        (wave_id,),
    )
    names = []
    for row in cursor.fetchall() or []:
        names.append(row["username"] if isinstance(row, dict) else row[0])
    return names


def replace_wave_members(wave_id: int, usernames: List[str], db_path: str = DB_PATH) -> List[str]:
    cleaned = sorted({str(name).strip() for name in usernames if str(name).strip()})
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        if not _table_exists(c, "engagement_wave_members"):
            return cleaned
        c.execute("DELETE FROM engagement_wave_members WHERE wave_id = ?", (wave_id,))
        for name in cleaned:
            c.execute(
                "INSERT INTO engagement_wave_members (wave_id, username) VALUES (?, ?)",
                (wave_id, name),
            )
        conn.commit()
    return cleaned


def list_wave_members(wave_id: int, db_path: str = DB_PATH) -> List[str]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        return _list_wave_members(c, wave_id)


def find_open_wave_for_env(
    application_id: int, environment_id: int, db_path: str = DB_PATH
) -> Optional[Dict[str, Any]]:
    target = int(environment_id)
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if not _table_exists(c, "engagement_waves"):
            return None
        c.execute(
            """
            SELECT * FROM engagement_waves
            WHERE application_id = ? AND status = 'open'
            ORDER BY opened_at DESC
            """,
            (application_id,),
        )
        for row in c.fetchall() or []:
            item = _hydrate_wave(dict(row), _list_wave_members(c, int(row["id"])))
            if target in wave_env_ids(item):
                return item
    return None


def list_waves(application_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if not _table_exists(c, "engagement_waves"):
            return []
        columns = get_table_columns(c, "engagement_waves")
        env_join = (
            "LEFT JOIN environments e ON e.id = w.environment_id"
            if "environment_id" in columns
            else "LEFT JOIN environments e ON FALSE"
        )
        env_select = ", e.slug AS environment_slug, e.display_name AS environment_name"
        c.execute(
            f"""
            SELECT w.* {env_select}
            FROM engagement_waves w
            {env_join}
            WHERE w.application_id = ?
            ORDER BY w.opened_at DESC
            """,
            (application_id,),
        )
        rows = []
        for row in c.fetchall() or []:
            item = _hydrate_wave(dict(row))
            item["members"] = _list_wave_members(c, int(item["id"]))
            rows.append(item)
        env_counts: Dict[int, int] = {}
        c.execute(
            """
            SELECT environment_id, COUNT(*) AS n
            FROM records
            WHERE application_id = ? AND environment_id IS NOT NULL
            GROUP BY environment_id
            """,
            (application_id,),
        )
        for row in c.fetchall() or []:
            try:
                env_counts[int(row["environment_id"])] = int(row["n"] or 0)
            except (TypeError, ValueError, KeyError):
                continue
        for item in rows:
            item["host_count"] = sum(env_counts.get(env_id, 0) for env_id in wave_env_ids(item))
    return rows


def create_wave(
    application_id: int,
    name: str,
    env_ids: List[int],
    opened_by: str,
    notes: str = "",
    members: Optional[List[str]] = None,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    cleaned_envs = []
    seen = set()
    for item in env_ids or []:
        try:
            env_id = int(item)
        except (TypeError, ValueError):
            continue
        if env_id in seen:
            continue
        seen.add(env_id)
        cleaned_envs.append(env_id)
    primary = cleaned_envs[0] if cleaned_envs else None
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        columns = get_table_columns(c, "engagement_waves")
        env_ids_json = json.dumps(cleaned_envs)
        if "environment_id" in columns:
            c.execute(
                """
                INSERT INTO engagement_waves (
                    application_id, name, status, env_ids, host_snapshot, opened_by, notes, environment_id
                )
                VALUES (?, ?, 'open', ?, ?, ?, ?, ?)
                RETURNING *
                """,
                (
                    application_id,
                    name,
                    env_ids_json,
                    json.dumps([]),
                    opened_by,
                    notes or "",
                    primary,
                ),
            )
        else:
            c.execute(
                """
                INSERT INTO engagement_waves (
                    application_id, name, status, env_ids, host_snapshot, opened_by, notes
                )
                VALUES (?, ?, 'open', ?, ?, ?, ?)
                RETURNING *
                """,
                (
                    application_id,
                    name,
                    env_ids_json,
                    json.dumps([]),
                    opened_by,
                    notes or "",
                ),
            )
        row = dict(c.fetchone())
        wave_id = int(row["id"])
        seeded = sorted(
            {str(opened_by or "").strip()} | {str(item).strip() for item in (members or []) if str(item).strip()}
        )
        seeded = [item for item in seeded if item]
        if _table_exists(c, "engagement_wave_members"):
            for item in seeded:
                c.execute(
                    "INSERT INTO engagement_wave_members (wave_id, username) VALUES (?, ?)",
                    (wave_id, item),
                )
        conn.commit()
    return _hydrate_wave(row, seeded)


def close_wave(wave_id: int, application_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            UPDATE engagement_waves
            SET status = 'closed', closed_at = NOW()
            WHERE id = ? AND application_id = ? AND status = 'open'
            RETURNING *
            """,
            (wave_id, application_id),
        )
        row = c.fetchone()
        conn.commit()
    if not row:
        return None
    wave = _hydrate_wave(dict(row))
    set_live_wave_host_status(wave, "Completed", db_path=db_path)
    return wave


def start_wave(wave_id: int, application_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        cols = get_table_columns(c, "engagement_waves")
        if "started_at" not in cols:
            c.execute(
                "SELECT * FROM engagement_waves WHERE id = ? AND application_id = ? AND status = 'open'",
                (wave_id, application_id),
            )
            row = c.fetchone()
            conn.commit()
            return _hydrate_wave(dict(row)) if row else None
        c.execute(
            """
            UPDATE engagement_waves
            SET started_at = NOW()
            WHERE id = ? AND application_id = ? AND status = 'open' AND started_at IS NULL
            RETURNING *
            """,
            (wave_id, application_id),
        )
        row = c.fetchone()
        conn.commit()
    if not row:
        return None
    wave = _hydrate_wave(dict(row))
    set_live_wave_host_status(wave, "In Progress", db_path=db_path)
    return wave


def get_wave(wave_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if not _table_exists(c, "engagement_waves"):
            return None
        c.execute("SELECT * FROM engagement_waves WHERE id = ?", (wave_id,))
        row = c.fetchone()
        if not row:
            return None
        item = dict(row)
        members = _list_wave_members(c, int(item["id"]))
    return _hydrate_wave(item, members)


def replace_wave_env_ids(wave_id: int, env_ids: List[int], db_path: str = DB_PATH) -> Dict[str, Any]:
    cleaned = []
    seen = set()
    for item in env_ids or []:
        try:
            env_id = int(item)
        except (TypeError, ValueError):
            continue
        if env_id in seen:
            continue
        seen.add(env_id)
        cleaned.append(env_id)
    primary = cleaned[0] if cleaned else None
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        columns = get_table_columns(c, "engagement_waves")
        if "environment_id" in columns:
            c.execute(
                "UPDATE engagement_waves SET env_ids = ?, environment_id = ? WHERE id = ? RETURNING *",
                (json.dumps(cleaned), primary, wave_id),
            )
        else:
            c.execute(
                "UPDATE engagement_waves SET env_ids = ? WHERE id = ? RETURNING *",
                (json.dumps(cleaned), wave_id),
            )
        row = c.fetchone()
        members = _list_wave_members(c, wave_id) if row else []
        conn.commit()
    if not row:
        return {}
    return _hydrate_wave(dict(row), members)


def list_live_wave_hosts(wave: Dict[str, Any], db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    env_ids = wave_env_ids(wave)
    if not env_ids:
        return []
    application_id = int(wave.get("application_id") or 0)
    wave_id = int(wave.get("id") or 0)
    placeholders = ",".join("?" for _ in env_ids)
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        pentest_cols = get_table_columns(c, "pentest_data")
        scan_sql = (
            ", COALESCE(p.scan_status, 'idle') AS scan_status"
            if "scan_status" in pentest_cols
            else ", 'idle' AS scan_status"
        )
        occ_cols = get_table_columns(c, "finding_occurrences")
        finding_cols = get_table_columns(c, "pentest_findings")
        wave_filtered = "record_id" in occ_cols and "discovered_wave_id" in finding_cols and wave_id
        if wave_filtered:
            occ_sql = """
                ,
                (SELECT COUNT(*) FROM finding_occurrences o
                 JOIN pentest_findings f ON f.id = o.finding_id
                 WHERE o.record_id = r.id AND f.discovered_wave_id = ?) AS finding_count,
                (SELECT COUNT(*) FROM finding_occurrences o
                 JOIN pentest_findings f ON f.id = o.finding_id
                 WHERE o.record_id = r.id AND f.discovered_wave_id = ?
                   AND o.status IN ('open', 'draft', 'retest')) AS open_occurrence_count
            """
        elif "record_id" in occ_cols:
            occ_sql = """
                ,
                (SELECT COUNT(*) FROM finding_occurrences o WHERE o.record_id = r.id) AS finding_count,
                (SELECT COUNT(*) FROM finding_occurrences o
                 WHERE o.record_id = r.id AND o.status IN ('open', 'draft', 'retest')) AS open_occurrence_count
            """
        else:
            occ_sql = ", 0 AS finding_count, 0 AS open_occurrence_count"
        scope_join = ""
        scope_select = ", TRUE AS in_scope"
        if _table_exists(c, "engagement_wave_hosts"):
            scope_join = "LEFT JOIN engagement_wave_hosts wh ON wh.wave_id = ? AND wh.record_id = r.id"
            scope_select = ", COALESCE(wh.in_scope, TRUE) AS in_scope"
        params: List[Any] = []
        if scope_join:
            params.append(wave_id)
        if wave_filtered:
            params.extend([wave_id, wave_id])
        params.extend([application_id, *env_ids])
        c.execute(
            f"""
            SELECT
                r.id, r.name, r.ip_address, r.environment_id,
                e.slug AS environment_slug, e.display_name AS environment_name,
                COALESCE(p.status, 'Not Started') AS pentest_status,
                COALESCE(p.tested_by, '') AS tested_by
                {scan_sql}
                {scope_select}
                {occ_sql}
            FROM records r
            LEFT JOIN environments e ON e.id = r.environment_id
            LEFT JOIN pentest_data p ON p.record_id = r.id
            {scope_join}
            WHERE r.application_id = ?
              AND r.environment_id IN ({placeholders})
            ORDER BY r.name
            """,
            tuple(params),
        )
        return [dict(row) for row in c.fetchall() or []]


def live_wave_host_ids(wave: Dict[str, Any], db_path: str = DB_PATH) -> List[int]:
    return [int(item["id"]) for item in list_live_wave_hosts(wave, db_path=db_path)]


def set_records_pentest_status(record_ids: List[int], status: str, db_path: str = DB_PATH) -> int:
    allowed = {"Not Started", "In Progress", "Completed"}
    if status not in allowed:
        return 0
    ids = [int(item) for item in record_ids or []]
    if not ids:
        return 0
    updated = 0
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        for record_id in ids:
            c.execute("SELECT id FROM pentest_data WHERE record_id = ?", (record_id,))
            if c.fetchone():
                c.execute(
                    "UPDATE pentest_data SET status = ? WHERE record_id = ?",
                    (status, record_id),
                )
            else:
                c.execute(
                    """
                    INSERT INTO pentest_data (record_id, dns_name, ip_address, source, status)
                    SELECT r.id, r.name, COALESCE(r.ip_address, ''), COALESCE(r.source, 'manual'), ?
                    FROM records r
                    WHERE r.id = ?
                    """,
                    (status, record_id),
                )
            updated += 1
        conn.commit()
    return updated


def set_live_wave_host_status(wave: Dict[str, Any], status: str, db_path: str = DB_PATH) -> int:
    return set_records_pentest_status(live_wave_host_ids(wave, db_path=db_path), status, db_path=db_path)


def set_wave_host_scope(
    wave_id: int,
    record_ids: List[int],
    in_scope: bool,
    db_path: str = DB_PATH,
) -> int:
    ids = [int(item) for item in record_ids or []]
    if not ids:
        return 0
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        if not _table_exists(c, "engagement_wave_hosts"):
            return 0
        for record_id in ids:
            c.execute(
                """
                INSERT INTO engagement_wave_hosts (wave_id, record_id, in_scope)
                VALUES (?, ?, ?)
                ON CONFLICT (wave_id, record_id) DO UPDATE SET in_scope = EXCLUDED.in_scope
                """,
                (wave_id, record_id, bool(in_scope)),
            )
        conn.commit()
    return len(ids)


def delete_wave(wave_id: int, application_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        finding_cols = get_table_columns(c, "pentest_findings")
        if "discovered_wave_id" in finding_cols:
            c.execute(
                "UPDATE pentest_findings SET discovered_wave_id = NULL WHERE discovered_wave_id = ?",
                (wave_id,),
            )
        c.execute(
            "DELETE FROM engagement_waves WHERE id = ? AND application_id = ?",
            (wave_id, application_id),
        )
        deleted = c.rowcount
        conn.commit()
    return bool(deleted)


def list_acl(environment_id: int, db_path: str = DB_PATH) -> List[str]:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        if not _table_exists(c, "environment_acl"):
            return []
        c.execute(
            "SELECT username FROM environment_acl WHERE environment_id = ? ORDER BY username",
            (environment_id,),
        )
        names = []
        for row in c.fetchall() or []:
            names.append(row["username"] if isinstance(row, dict) else row[0])
    return names


def replace_acl(environment_id: int, usernames: List[str], db_path: str = DB_PATH) -> List[str]:
    cleaned = sorted({str(name).strip() for name in usernames if str(name).strip()})
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM environment_acl WHERE environment_id = ?", (environment_id,))
        for name in cleaned:
            c.execute(
                "INSERT INTO environment_acl (environment_id, username) VALUES (?, ?)",
                (environment_id, name),
            )
        conn.commit()
    return cleaned


def allowed_environment_ids(
    application_id: int,
    username: str,
    *,
    is_override: bool,
    app_lead: str = "",
    db_path: str = DB_PATH,
) -> Optional[List[int]]:
    """None means unrestricted. List means only those env ids."""
    if is_override or (app_lead and username == app_lead):
        return None
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if not _table_exists(c, "environment_acl"):
            return None
        c.execute("SELECT id FROM environments WHERE application_id = ?", (application_id,))
        env_ids = [int(row["id"] if isinstance(row, dict) else row[0]) for row in c.fetchall() or []]
        restricted = []
        open_envs = []
        for env_id in env_ids:
            c.execute(
                "SELECT username FROM environment_acl WHERE environment_id = ?",
                (env_id,),
            )
            names = [
                row["username"] if isinstance(row, dict) else row[0]
                for row in c.fetchall() or []
            ]
            if not names:
                open_envs.append(env_id)
            elif username in names:
                restricted.append(env_id)
        allowed = sorted(set(open_envs + restricted))
        if set(allowed) == set(env_ids):
            return None
        return allowed


def list_env_checklists(environment_id: int, db_path: str = DB_PATH) -> List[str]:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        if not _table_exists(c, "environment_checklists"):
            return []
        c.execute(
            "SELECT template_key FROM environment_checklists WHERE environment_id = ? ORDER BY template_key",
            (environment_id,),
        )
        return [row["template_key"] if isinstance(row, dict) else row[0] for row in c.fetchall() or []]


def replace_env_checklists(environment_id: int, keys: List[str], db_path: str = DB_PATH) -> List[str]:
    cleaned = sorted({str(key).strip() for key in keys if str(key).strip()})
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM environment_checklists WHERE environment_id = ?", (environment_id,))
        for key in cleaned:
            c.execute(
                "INSERT INTO environment_checklists (environment_id, template_key) VALUES (?, ?)",
                (environment_id, key),
            )
        conn.commit()
    return cleaned


def list_zones(application_id: Optional[int] = None, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if not _table_exists(c, "dns_zones"):
            return []
        if application_id:
            c.execute(
                """
                SELECT * FROM dns_zones
                WHERE application_id = ? OR application_id IS NULL
                ORDER BY suffix
                """,
                (application_id,),
            )
        else:
            c.execute("SELECT * FROM dns_zones ORDER BY suffix")
        return [dict(row) for row in c.fetchall() or []]


def create_zone(suffix: str, display_name: str, application_id: Optional[int], notes: str = "", db_path: str = DB_PATH) -> Dict[str, Any]:
    cleaned = str(suffix or "").strip().lower().lstrip(".")
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO dns_zones (suffix, display_name, application_id, notes)
            VALUES (?, ?, ?, ?)
            RETURNING *
            """,
            (cleaned, display_name or cleaned, application_id, notes or ""),
        )
        row = dict(c.fetchone())
        conn.commit()
    return row


def delete_zone(zone_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM dns_zones WHERE id = ?", (zone_id,))
        deleted = c.rowcount > 0
        conn.commit()
    return deleted


def share_host(record_id: int, owner_application_id: int, consumer_application_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id FROM records WHERE id = ? AND application_id = ?",
            (record_id, owner_application_id),
        )
        if not c.fetchone():
            return False
        c.execute(
            """
            INSERT INTO shared_host_apps (record_id, consumer_application_id)
            SELECT ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM shared_host_apps
                WHERE record_id = ? AND consumer_application_id = ?
            )
            """,
            (record_id, consumer_application_id, record_id, consumer_application_id),
        )
        conn.commit()
    return True


def list_shared_hosts(consumer_application_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        if not _table_exists(c, "shared_host_apps"):
            return []
        c.execute(
            """
            SELECT r.id, r.name, r.application_id AS owner_application_id, a.name AS owner_application_name
            FROM shared_host_apps s
            JOIN records r ON r.id = s.record_id
            LEFT JOIN applications a ON a.id = r.application_id
            WHERE s.consumer_application_id = ?
            ORDER BY r.name
            """,
            (consumer_application_id,),
        )
        return [dict(row) for row in c.fetchall() or []]


def host_visible_to_app(cursor, record_id: int, application_id: int) -> bool:
    cursor.execute(
        "SELECT id FROM records WHERE id = ? AND application_id = ?",
        (record_id, application_id),
    )
    if cursor.fetchone():
        return True
    if not _table_exists(cursor, "shared_host_apps"):
        return False
    cursor.execute(
        "SELECT 1 FROM shared_host_apps WHERE record_id = ? AND consumer_application_id = ?",
        (record_id, application_id),
    )
    return cursor.fetchone() is not None


def count_running_scans_for_env(environment_id: int, db_path: str = DB_PATH) -> int:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM pentest_data p
            JOIN records r ON r.id = p.record_id
            WHERE r.environment_id = ? AND p.scan_status = 'running'
            """,
            (environment_id,),
        )
        row = c.fetchone() or {}
    return int(row["cnt"] if isinstance(row, dict) else (row[0] if row else 0) or 0)


def fetch_host_env(record_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT e.id, e.slug, e.allow_destructive, e.max_concurrent_scans, e.application_id
            FROM records r
            LEFT JOIN environments e ON e.id = r.environment_id
            WHERE r.id = ?
            """,
            (record_id,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def _snapshot_ids(wave: Dict[str, Any]) -> List[int]:
    return live_wave_host_ids(wave)


def assign_record_testers(record_ids: List[int], username: str, db_path: str = DB_PATH) -> int:
    cleaned = str(username or "").strip()
    ids = [int(item) for item in record_ids or []]
    if not cleaned or not ids:
        return 0
    updated = 0
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        for record_id in ids:
            c.execute("SELECT id FROM pentest_data WHERE record_id = ?", (record_id,))
            if c.fetchone():
                c.execute(
                    """
                    UPDATE pentest_data
                    SET tested_by = ?
                    WHERE record_id = ?
                    """,
                    (cleaned, record_id),
                )
            else:
                c.execute(
                    """
                    INSERT INTO pentest_data (record_id, dns_name, ip_address, source, tested_by, status)
                    SELECT r.id, r.name, COALESCE(r.ip_address, ''), COALESCE(r.source, 'manual'), ?, 'Not Started'
                    FROM records r
                    WHERE r.id = ?
                    """,
                    (cleaned, record_id),
                )
            if _table_exists(c, "pentest_collaborators"):
                c.execute(
                    "DELETE FROM pentest_collaborators WHERE record_id = ? AND username = ?",
                    (record_id, cleaned),
                )
            updated += 1
        conn.commit()
    return updated


def sync_wave_host_collaborators(
    wave_id: int,
    usernames: Optional[List[str]] = None,
    db_path: str = DB_PATH,
) -> None:
    wave = get_wave(wave_id, db_path=db_path)
    if not wave:
        return
    snapshot = live_wave_host_ids(wave, db_path=db_path)
    members = usernames if usernames is not None else (wave.get("members") or [])
    cleaned = sorted({str(name).strip() for name in members if str(name).strip()})
    marker = f"wave:{int(wave_id)}"
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        if not snapshot or not _table_exists(c, "pentest_collaborators"):
            return
        for record_id in snapshot:
            c.execute(
                "DELETE FROM pentest_collaborators WHERE record_id = ? AND added_by = ?",
                (record_id, marker),
            )
            owner = ""
            c.execute("SELECT tested_by FROM pentest_data WHERE record_id = ?", (record_id,))
            row = c.fetchone()
            if row:
                owner = str((row["tested_by"] if isinstance(row, dict) else row[0]) or "").strip()
            for name in cleaned:
                if name == owner:
                    continue
                try:
                    c.execute(
                        """
                        INSERT INTO pentest_collaborators (record_id, username, added_by, added_at)
                        VALUES (?, ?, ?, NOW() + INTERVAL '4 hours')
                        ON CONFLICT (record_id, username) DO NOTHING
                        """,
                        (record_id, name, marker),
                    )
                except Exception:
                    c.execute(
                        "SELECT 1 FROM pentest_collaborators WHERE record_id = ? AND username = ?",
                        (record_id, name),
                    )
                    if not c.fetchone():
                        c.execute(
                            """
                            INSERT INTO pentest_collaborators (record_id, username, added_by, added_at)
                            VALUES (?, ?, ?, NOW() + INTERVAL '4 hours')
                            """,
                            (record_id, name, marker),
                        )
        conn.commit()
