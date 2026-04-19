import json
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import IntegrityError, ROW_AS_DICT, get_db_connection

SERVICE_API_SCOPES = {"records.read", "pentests.read", "pentests.write"}


def _load_scopes(raw_scopes: Any) -> List[str]:
    if not raw_scopes:
        return []
    try:
        parsed = json.loads(raw_scopes) if isinstance(raw_scopes, str) else raw_scopes
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    deduped = []
    for scope in parsed:
        normalized = str(scope or "").strip().lower()
        if normalized in SERVICE_API_SCOPES and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _normalize_service_account_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    payload = dict(row)
    payload["scopes"] = _load_scopes(payload.get("scopes"))
    payload["is_service_account"] = bool(payload.get("is_service_account"))
    payload["has_api_key"] = bool(payload.get("api_key"))
    return payload


def list_service_accounts(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT
                u.id AS service_account_id,
                u.username,
                u.added_date,
                u.is_service_account,
                k.api_key,
                k.scopes,
                k.created_at AS key_created_at,
                k.expires_at,
                k.rotated_at,
                k.last_used_at,
                k.created_by,
                k.rotated_by
            FROM allowed_users u
            LEFT JOIN service_account_api_keys k ON k.service_account_id = u.id
            WHERE u.is_service_account = 1
            ORDER BY u.username ASC
            """
        )
        rows = c.fetchall()
    return [_normalize_service_account_row(dict(row)) for row in rows if row]


def get_service_account_by_username(username: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id AS service_account_id, username, added_date, is_service_account
            FROM allowed_users
            WHERE username = ?
              AND is_service_account = 1
            LIMIT 1
            """,
            (username,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def get_service_account_with_key(username: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT
                u.id AS service_account_id,
                u.username,
                u.added_date,
                u.is_service_account,
                k.id AS key_id,
                k.api_key,
                k.api_key_fingerprint,
                k.scopes,
                k.created_at AS key_created_at,
                k.expires_at,
                k.rotated_at,
                k.last_used_at,
                k.created_by,
                k.rotated_by
            FROM allowed_users u
            LEFT JOIN service_account_api_keys k ON k.service_account_id = u.id
            WHERE u.username = ?
              AND u.is_service_account = 1
            LIMIT 1
            """,
            (username,),
        )
        row = c.fetchone()
    return _normalize_service_account_row(dict(row)) if row else None


def create_service_account(username: str, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO allowed_users (
                username,
                email,
                added_date,
                role,
                auth_type,
                password,
                must_reset,
                permissions,
                is_service_account
            )
            VALUES (?, '', (NOW() + INTERVAL '4 hours'), 'user', 'service', NULL, 0, '[]', 1)
            """,
            (username,),
        )
        conn.commit()


def create_service_account_key(
    service_account_id: int,
    api_key: str,
    api_key_fingerprint: str,
    scopes_json: str,
    created_at: str,
    expires_at: str,
    actor_username: str,
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO service_account_api_keys (
                service_account_id,
                api_key,
                api_key_fingerprint,
                scopes,
                created_at,
                expires_at,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                service_account_id,
                api_key,
                api_key_fingerprint,
                scopes_json,
                created_at,
                expires_at,
                actor_username,
            ),
        )
        key_id = c.rowcount
        conn.commit()
    return key_id


def rotate_service_account_key(
    service_account_id: int,
    api_key: str,
    api_key_fingerprint: str,
    scopes_json: str,
    rotated_at: str,
    expires_at: str,
    actor_username: str,
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE service_account_api_keys
            SET api_key = ?,
                api_key_fingerprint = ?,
                scopes = ?,
                rotated_at = ?,
                expires_at = ?,
                rotated_by = ?
            WHERE service_account_id = ?
            """,
            (
                api_key,
                api_key_fingerprint,
                scopes_json,
                rotated_at,
                expires_at,
                actor_username,
                service_account_id,
            ),
        )
        rowcount = c.rowcount
        conn.commit()
    return rowcount


def update_service_account_scopes(
    service_account_id: int,
    scopes_json: str,
    db_path: str = DB_PATH,
) -> int:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE service_account_api_keys
            SET scopes = ?
            WHERE service_account_id = ?
            """,
            (scopes_json, service_account_id),
        )
        rowcount = c.rowcount
        conn.commit()
    return rowcount


def get_service_account_key_by_fingerprint(
    api_key_fingerprint: str,
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT
                k.id AS key_id,
                k.api_key,
                k.api_key_fingerprint,
                k.scopes,
                k.expires_at,
                k.last_used_at,
                u.id AS service_account_id,
                u.username,
                u.is_service_account
            FROM service_account_api_keys k
            INNER JOIN allowed_users u ON u.id = k.service_account_id
            WHERE k.api_key_fingerprint = ?
              AND u.is_service_account = 1
            LIMIT 1
            """,
            (api_key_fingerprint,),
        )
        row = c.fetchone()
    return _normalize_service_account_row(dict(row)) if row else None


def touch_service_api_key_last_used(key_id: int, used_at: str, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE service_account_api_keys
            SET last_used_at = ?
            WHERE id = ?
            """,
            (used_at, key_id),
        )
        conn.commit()


PENTEST_WRITABLE_FIELDS = {
    "open_ports",
    "status",
    "scan_status",
    "tested_by",
    "test_start_date",
    "test_end_date",
    "vulnerable",
    "vulnerability_fixed",
    "notes",
    "vulnerabilities",
    "checklist_states",
}

VALID_SCAN_STATUSES = {"idle", "running", "completed", "failed"}


def fetch_pentest_row(record_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
        row = c.fetchone()
    return dict(row) if row else None


def fetch_single_pentest_dataset(record_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT
                p.id,
                p.record_id,
                p.dns_name,
                p.ip_address,
                p.source,
                p.report_file,
                p.generated_report_file,
                p.generated_report_template_id,
                p.generated_report_generated_at,
                p.vulnerable,
                p.tested_by,
                p.test_start_date,
                p.test_end_date,
                p.vulnerability_fixed,
                p.service_desk_link,
                p.status,
                p.scan_status,
                p.open_ports,
                p.notes,
                p.owasp_checklist,
                p.checklist_states,
                p.vulnerabilities,
                r.name AS record_name,
                r.description AS record_description,
                r.application_owner,
                r.maintainer,
                r.status AS record_status,
                r.creation_date AS record_creation_date,
                r.last_modification_date AS record_last_modification_date,
                r.application_id,
                a.name AS application_name
            FROM pentest_data p
            INNER JOIN records r ON r.id = p.record_id
            LEFT JOIN applications a ON a.id = r.application_id
            WHERE p.record_id = ?
            """,
            (record_id,),
        )
        row = c.fetchone()
    return dict(row) if row else None


def update_pentest_fields(record_id: int, fields: Dict[str, Any], db_path: str = DB_PATH) -> bool:
    """Merge provided fields into existing pentest row. Returns False if record not found."""
    existing = fetch_pentest_row(record_id, db_path)
    if existing is None:
        return False
    updates = {k: v for k, v in fields.items() if k in PENTEST_WRITABLE_FIELDS}
    if not updates:
        return True
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [record_id]
        c.execute(f"UPDATE pentest_data SET {set_clause} WHERE record_id = ?", values)
        conn.commit()
    return True


def append_pentest_vulnerability(
    record_id: int, vulnerability: Dict[str, Any], db_path: str = DB_PATH
) -> bool:
    """Atomically append one vulnerability to the pentest row. Returns False if record not found."""
    import json as _json
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            "SELECT vulnerabilities FROM pentest_data WHERE record_id = ? FOR UPDATE",
            (record_id,),
        )
        row = c.fetchone()
        if row is None:
            return False
        raw = row["vulnerabilities"] if isinstance(row, dict) else (row[0] if row else None)
        try:
            existing = _json.loads(raw) if raw else []
            if not isinstance(existing, list):
                existing = []
        except (_json.JSONDecodeError, TypeError):
            existing = []
        existing.append(vulnerability)
        c.execute(
            "UPDATE pentest_data SET vulnerabilities = ? WHERE record_id = ?",
            (_json.dumps(existing), record_id),
        )
        conn.commit()
    return True


def fetch_checklist_templates_dataset(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT id, key, name, service, auto_ports, sections, enabled
            FROM service_checklists
            ORDER BY name ASC
            """
        )
        rows = c.fetchall()
    return [dict(row) for row in rows]


def fetch_records_dataset(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT
                r.id,
                r.name,
                r.ip_address,
                r.source,
                r.status,
                r.origin,
                r.sync_conflict,
                r.sync_conflict_reason,
                r.creation_date,
                r.last_modification_date,
                r.application_owner,
                r.maintainer,
                r.description,
                r.application_id,
                a.name AS application_name
            FROM records r
            LEFT JOIN applications a ON a.id = r.application_id
            ORDER BY r.id ASC
            """
        )
        rows = c.fetchall()

    payload = []
    for row in rows:
        item = dict(row)
        pentest_id = item.get("pentest_id")
        record_data = {
            "id": item.get("id"),
            "name": item.get("name"),
            "ip_address": item.get("ip_address"),
            "source": item.get("source"),
            "status": item.get("status"),
            "origin": item.get("origin"),
            "sync_conflict": item.get("sync_conflict"),
            "sync_conflict_reason": item.get("sync_conflict_reason"),
            "creation_date": item.get("creation_date"),
            "last_modification_date": item.get("last_modification_date"),
            "application_owner": item.get("application_owner"),
            "maintainer": item.get("maintainer"),
            "description": item.get("description"),
            "application_id": item.get("application_id"),
            "application_name": item.get("application_name"),
            "pentest": None,
        }
        if pentest_id is not None:
            record_data["pentest"] = {
                "id": pentest_id,
                "record_id": item.get("pentest_record_id"),
                "dns_name": item.get("pentest_dns_name"),
                "ip_address": item.get("pentest_ip_address"),
                "source": item.get("pentest_source"),
                "report_file": item.get("pentest_report_file"),
                "generated_report_file": item.get("pentest_generated_report_file"),
                "generated_report_template_id": item.get("pentest_generated_report_template_id"),
                "generated_report_generated_at": item.get("pentest_generated_report_generated_at"),
                "vulnerable": item.get("pentest_vulnerable"),
                "tested_by": item.get("pentest_tested_by"),
                "test_start_date": item.get("pentest_test_start_date"),
                "test_end_date": item.get("pentest_test_end_date"),
                "vulnerability_fixed": item.get("pentest_vulnerability_fixed"),
                "service_desk_link": item.get("pentest_service_desk_link"),
                "status": item.get("pentest_status"),
                "open_ports": item.get("pentest_open_ports"),
                "notes": item.get("pentest_notes"),
                "owasp_checklist": item.get("pentest_owasp_checklist"),
                "checklist_states": item.get("pentest_checklist_states"),
                "vulnerabilities": item.get("pentest_vulnerabilities"),
            }
        payload.append(record_data)
    return payload


def fetch_pentests_dataset(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT
                p.id,
                p.record_id,
                p.dns_name,
                p.ip_address,
                p.source,
                p.report_file,
                p.generated_report_file,
                p.generated_report_template_id,
                p.generated_report_generated_at,
                p.vulnerable,
                p.tested_by,
                p.test_start_date,
                p.test_end_date,
                p.vulnerability_fixed,
                p.service_desk_link,
                p.status,
                p.open_ports,
                p.notes,
                p.owasp_checklist,
                p.checklist_states,
                p.vulnerabilities,
                r.name AS record_name,
                r.description AS record_description,
                r.application_owner,
                r.maintainer,
                r.status AS record_status,
                r.creation_date AS record_creation_date,
                r.last_modification_date AS record_last_modification_date,
                r.application_id,
                a.name AS application_name
            FROM pentest_data p
            INNER JOIN records r ON r.id = p.record_id
            LEFT JOIN applications a ON a.id = r.application_id
            ORDER BY p.record_id ASC
            """
        )
        rows = c.fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "IntegrityError",
    "PENTEST_WRITABLE_FIELDS",
    "SERVICE_API_SCOPES",
    "VALID_SCAN_STATUSES",
    "append_pentest_vulnerability",
    "create_service_account",
    "create_service_account_key",
    "fetch_checklist_templates_dataset",
    "fetch_pentest_row",
    "fetch_pentests_dataset",
    "fetch_records_dataset",
    "fetch_single_pentest_dataset",
    "get_service_account_by_username",
    "get_service_account_key_by_fingerprint",
    "get_service_account_with_key",
    "list_service_accounts",
    "rotate_service_account_key",
    "touch_service_api_key_last_used",
    "update_pentest_fields",
    "update_service_account_scopes",
]
