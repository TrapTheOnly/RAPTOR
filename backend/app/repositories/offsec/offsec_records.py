import json
import logging
from copy import deepcopy

from flask import session

from app.domain.offsec.shared import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.services.authorization_service import user_has_permission

logger = logging.getLogger(__name__)

DEFAULT_PENTEST = {
    "report_file": None,
    "generated_report_file": None,
    "generated_report_template_id": None,
    "generated_report_generated_at": None,
    "vulnerable": 0,
    "tested_by": None,
    "test_start_date": None,
    "test_end_date": None,
    "vulnerability_fixed": 0,
    "service_desk_link": None,
    "status": "Not Started",
    "open_ports": "",
    "notes": "",
    "owasp_checklist": "",
    "checklist_states": "",
    "vulnerabilities": "",
}

PENTEST_ACCESS_CAPABILITIES = {
    "owner": {
        "can_edit_lifecycle": True,
        "can_edit_security_details": True,
        "can_manage_collaborators": True,
        "can_create_finding": True,
        "can_generate_reports": True,
        "can_upload_manual_report": True,
        "can_delete_reports": True,
        "can_upload_images": True,
    },
    "collaborator": {
        "can_edit_lifecycle": False,
        "can_edit_security_details": True,
        "can_manage_collaborators": False,
        "can_create_finding": True,
        "can_generate_reports": True,
        "can_upload_manual_report": True,
        "can_delete_reports": False,
        "can_upload_images": True,
    },
    "manager_override": {
        "can_edit_lifecycle": True,
        "can_edit_security_details": True,
        "can_manage_collaborators": True,
        "can_create_finding": True,
        "can_generate_reports": True,
        "can_upload_manual_report": True,
        "can_delete_reports": True,
        "can_upload_images": True,
    },
    "admin_override": {
        "can_edit_lifecycle": True,
        "can_edit_security_details": True,
        "can_manage_collaborators": True,
        "can_create_finding": True,
        "can_generate_reports": True,
        "can_upload_manual_report": True,
        "can_delete_reports": True,
        "can_upload_images": True,
    },
    "viewer": {
        "can_edit_lifecycle": False,
        "can_edit_security_details": False,
        "can_manage_collaborators": False,
        "can_create_finding": False,
        "can_generate_reports": False,
        "can_upload_manual_report": False,
        "can_delete_reports": False,
        "can_upload_images": False,
    },
}


def _normalize_username(value):
    return str(value or "").strip()


def parse_vulnerabilities(raw_value):
    if isinstance(raw_value, list):
        parsed = deepcopy(raw_value)
    elif isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
        except Exception:
            parsed = []
    else:
        parsed = []
    return parsed if isinstance(parsed, list) else []


def normalize_vulnerabilities_for_response(raw_value, default_owner=""):
    normalized = []
    for index, vulnerability in enumerate(parse_vulnerabilities(raw_value)):
        if not isinstance(vulnerability, dict):
            continue
        current = dict(vulnerability)
        if current.get("id") in (None, ""):
            current["id"] = f"legacy-{index + 1}"
        if not current.get("created_by") and default_owner:
            current["created_by"] = default_owner
        normalized.append(current)
    return normalized


def serialize_vulnerabilities(vulnerabilities):
    return json.dumps(vulnerabilities, ensure_ascii=True)


def get_pentest_users_internal():
    """Fetches users with pentest-capable roles from the database."""
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            users = c.execute(
                "SELECT id, username FROM allowed_users WHERE role IN ('pentester', 'manager', 'admin')"
            ).fetchall()
            return [{"id": user["id"], "username": user["username"]} for user in users]
    except Exception as e:
        logger.error(f"Error fetching pentesters: {e}")
        return None


def _prune_ineligible_collaborators(cursor, record_id=None):
    query = """
        DELETE FROM pentest_collaborators
        WHERE username NOT IN (
            SELECT username
            FROM allowed_users
            WHERE role IN ('pentester', 'manager', 'admin')
        )
    """
    params = ()
    if record_id is not None:
        query += " AND record_id = ?"
        params = (record_id,)
    cursor.execute(query, params)


def get_record_details_internal(record_id):
    """Internal function to fetch record details."""
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute("SELECT * FROM records WHERE id = ?", (record_id,))
            return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching record details for ID {record_id}: {e}")
        return None


def get_pentest_row(record_id, cursor=None):
    try:
        if cursor is not None:
            cursor.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
            return cursor.fetchone()
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
            return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching pentest data for ID {record_id}: {e}")
        return None


def get_pentest_collaborators_internal(record_id=None, cursor=None):
    try:
        if cursor is not None:
            _prune_ineligible_collaborators(cursor, record_id=record_id)
            if record_id is None:
                cursor.execute(
                    """
                    SELECT record_id, username, added_by, added_at
                    FROM pentest_collaborators
                    ORDER BY LOWER(username) ASC
                    """
                )
                return [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT record_id, username, added_by, added_at
                FROM pentest_collaborators
                WHERE record_id = ?
                ORDER BY LOWER(username) ASC
                """,
                (record_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            return get_pentest_collaborators_internal(record_id=record_id, cursor=c)
    except Exception as e:
        logger.error(f"Error fetching pentest collaborators for record {record_id}: {e}")
        return [] if record_id is not None else {}


def get_collaborator_usernames(record_id, cursor=None):
    rows = get_pentest_collaborators_internal(record_id=record_id, cursor=cursor)
    return [_normalize_username(row.get("username")) for row in rows if _normalize_username(row.get("username"))]


def get_access_role_for_user(record_id, username=None, role=None, pentest_row=None, collaborators=None):
    normalized_username = _normalize_username(username)
    normalized_role = _normalize_username(role)

    if normalized_username and user_has_permission(
        normalized_username,
        normalized_role,
        "modify_others_pentests_admin",
    ):
        return "admin_override" if normalized_role == "admin" else "manager_override"

    row = pentest_row or get_pentest_row(record_id)
    assigned_user = _normalize_username(row["tested_by"] if row and row.get("tested_by") else "")
    if normalized_username and assigned_user and assigned_user == normalized_username:
        return "owner"

    collaborator_names = collaborators if collaborators is not None else get_collaborator_usernames(record_id)
    if normalized_username and normalized_username in {_normalize_username(item) for item in collaborator_names}:
        return "collaborator"

    return "viewer"


def get_pentest_access_role(record_id):
    return get_access_role_for_user(
        record_id,
        username=session.get("username"),
        role=session.get("user_type"),
    )


def get_pentest_capabilities(access_role):
    return dict(PENTEST_ACCESS_CAPABILITIES.get(access_role, PENTEST_ACCESS_CAPABILITIES["viewer"]))


def can_manage_collaborators(record_id, access_role=None, pentest_row=None):
    role = access_role or get_pentest_access_role(record_id)
    row = pentest_row or get_pentest_row(record_id)
    status = _normalize_username(row["status"] if row and row.get("status") else DEFAULT_PENTEST["status"])
    if status == "Completed":
        return False
    return role in {"owner", "manager_override", "admin_override"}


def can_remove_collaborator(record_id, target_username, access_role=None, collaborators=None):
    role = access_role or get_pentest_access_role(record_id)
    normalized_target = _normalize_username(target_username)
    collaborator_names = collaborators if collaborators is not None else get_collaborator_usernames(record_id)
    is_collaborator = normalized_target in {_normalize_username(item) for item in collaborator_names}
    if not is_collaborator:
        return False
    if role in {"manager_override", "admin_override"}:
        return True
    return role == "collaborator" and normalized_target == _normalize_username(session.get("username"))


def _build_record_payload(record, pentest, collaborators):
    access_role = get_access_role_for_user(
        record["id"],
        username=session.get("username"),
        role=session.get("user_type"),
        pentest_row=pentest,
        collaborators=collaborators,
    )
    normalized_owner = _normalize_username(pentest.get("tested_by")) if pentest else ""
    vulnerabilities = normalize_vulnerabilities_for_response(
        pentest.get("vulnerabilities") if pentest else "",
        default_owner=normalized_owner,
    )
    return {
        **DEFAULT_PENTEST,
        **(pentest or {}),
        "recordId": record["id"],
        "name": record["name"],
        "ip_address": record["ip_address"],
        "source": record["source"],
        "description": record.get("description", ""),
        "application_id": record.get("application_id"),
        "application_name": record.get("application_name"),
        "collaborators": collaborators,
        "access_role": access_role,
        "capabilities": get_pentest_capabilities(access_role),
        "vulnerabilities": vulnerabilities,
    }


def get_pentest_data_internal(record_id=None):
    """Internal function to fetch pentest data (all records or a single record)."""
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()

            if record_id is not None:
                c.execute(
                    """
                    SELECT
                        r.id,
                        r.name,
                        r.ip_address,
                        r.source,
                        r.status,
                        r.creation_date,
                        r.last_modification_date,
                        r.application_owner,
                        r.maintainer,
                        r.description,
                        r.application_id,
                        a.name AS application_name
                    FROM records r
                    LEFT JOIN applications a ON r.application_id = a.id
                    WHERE r.id = ?
                    """,
                    (record_id,),
                )
                record_row = c.fetchone()
                if not record_row:
                    return None
                record = dict(record_row)

                pentest_row = get_pentest_row(record_id, cursor=c)
                pentest = dict(pentest_row) if pentest_row else {}
                collaborators = get_collaborator_usernames(record_id, cursor=c)
                return _build_record_payload(record, pentest, collaborators)

            c.execute(
                """
                SELECT
                    r.id,
                    r.name,
                    r.ip_address,
                    r.source,
                    r.status,
                    r.creation_date,
                    r.last_modification_date,
                    r.application_owner,
                    r.maintainer,
                    r.description,
                    r.application_id,
                    a.name AS application_name
                FROM records r
                LEFT JOIN applications a ON r.application_id = a.id
                """
            )
            rows = c.fetchall()
            dns_records = [dict(ix) for ix in rows]

            c.execute("SELECT * FROM pentest_data")
            pentest_records = {row["record_id"]: dict(row) for row in c.fetchall()}

            collaborator_map = {}
            for collaborator in get_pentest_collaborators_internal(cursor=c):
                collaborator_map.setdefault(collaborator["record_id"], []).append(collaborator["username"])

            return [
                _build_record_payload(
                    record,
                    pentest_records.get(record["id"], {}),
                    collaborator_map.get(record["id"], []),
                )
                for record in dns_records
            ]

    except Exception as e:
        logger.error(f"Error fetching record details: {e}")
        return None


def enforce_pentest_record_access(record_id, action_verb="access", allowed_roles=None):
    """
    Enforce record-level access for pentest resources.
    allowed_roles defaults to owner/collaborator/admin override/manager override.
    """
    access_role = get_pentest_access_role(record_id)
    allowed = set(allowed_roles or {"owner", "collaborator", "manager_override", "admin_override"})
    if access_role in allowed:
        return True, None

    pentest_row = get_pentest_row(record_id)
    assigned_user = _normalize_username(pentest_row["tested_by"] if pentest_row and pentest_row.get("tested_by") else "")
    if not assigned_user:
        return False, f"Unassigned pentest records must be assigned before {action_verb}."
    return False, f"You are not allowed to {action_verb} this pentest."


__all__ = [
    "DEFAULT_PENTEST",
    "_prune_ineligible_collaborators",
    "can_manage_collaborators",
    "can_remove_collaborator",
    "enforce_pentest_record_access",
    "get_access_role_for_user",
    "get_collaborator_usernames",
    "get_pentest_access_role",
    "get_pentest_capabilities",
    "get_pentest_collaborators_internal",
    "get_pentest_data_internal",
    "get_pentest_row",
    "get_pentest_users_internal",
    "get_record_details_internal",
    "normalize_vulnerabilities_for_response",
    "parse_vulnerabilities",
    "serialize_vulnerabilities",
]
