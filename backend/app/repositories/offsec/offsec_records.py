import logging

from flask import session

from app.domain.offsec.shared import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.services.authorization_service import user_has_permission

logger = logging.getLogger(__name__)


def get_pentest_data_internal(record_id=None):
    """Internal function to fetch pentest data (all records or a single record)."""
    default_pentest = {
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

                c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
                pentest_row = c.fetchone()
                pentest = dict(pentest_row) if pentest_row else default_pentest

                return {
                    **pentest,
                    "recordId": record["id"],
                    "name": record["name"],
                    "ip_address": record["ip_address"],
                    "source": record["source"],
                    "description": record.get("description", ""),
                    "application_id": record.get("application_id"),
                    "application_name": record.get("application_name"),
                }

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

            return [
                {
                    **pentest_records.get(record["id"], default_pentest),
                    "recordId": record["id"],
                    "name": record["name"],
                    "ip_address": record["ip_address"],
                    "source": record["source"],
                    "description": record.get("description", ""),
                    "application_id": record.get("application_id"),
                    "application_name": record.get("application_name"),
                }
                for record in dns_records
            ]

    except Exception as e:
        logger.error(f"Error fetching record details: {e}")
        return None


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


def get_pentest_users_internal():
    """Fetches users with the 'pentest' role from the database."""
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            users = c.execute(
                "SELECT id, username FROM allowed_users WHERE role IN ('pentester', 'manager')"
            ).fetchall()
            return [{"id": user["id"], "username": user["username"]} for user in users]
    except Exception as e:
        logger.error(f"Error fetching pentesters: {e}")
        return None


def get_pentest_row(record_id):
    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
            return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching pentest data for ID {record_id}: {e}")
        return None


def enforce_pentest_record_access(record_id, action_verb="access"):
    """
    Enforce record-level access for pentest resources.
    - Admin/manager users with 'modify_others_pentests_admin' can access any record.
    - Others can access only records assigned to their username.
    - Unassigned records are blocked for non-privileged users.
    """
    username = session.get("username")
    role = session.get("user_type")
    can_modify_others = user_has_permission(username, role, "modify_others_pentests_admin")
    if can_modify_others:
        return True, None

    pentest_row = get_pentest_row(record_id)
    assigned_user = (pentest_row["tested_by"] if pentest_row and pentest_row["tested_by"] else "").strip()
    if not assigned_user:
        return False, f"Unassigned pentest records must be assigned before {action_verb}."
    if assigned_user != (username or "").strip():
        return False, f"You are not allowed to {action_verb} another user's pentest."
    return True, None


def filter_visible_pentest_records(records, username, can_modify_others=False):
    """
    Restrict pentest dashboard rows for non-privileged users.
    - Privileged users see all rows.
    - Others see rows assigned to themselves or currently unassigned.
    """
    if not isinstance(records, list):
        return []
    if can_modify_others:
        return list(records)

    normalized_username = (username or "").strip()
    visible_records = []
    for record in records:
        if not isinstance(record, dict):
            continue
        assigned_user = str(record.get("tested_by") or "").strip()
        if not assigned_user or assigned_user == normalized_username:
            visible_records.append(record)
    return visible_records


__all__ = [
    "enforce_pentest_record_access",
    "filter_visible_pentest_records",
    "get_pentest_data_internal",
    "get_pentest_row",
    "get_pentest_users_internal",
    "get_record_details_internal",
]
