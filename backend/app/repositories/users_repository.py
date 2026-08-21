from typing import Any, Dict, List, Optional, Tuple

from app.config import DB_PATH
from app.integrations.db.connection import get_db_connection
from app.repositories.admin_users_repository import ADMIN_USERNAME


def get_allowed_user_for_login(username: str, db_path: str = DB_PATH) -> Optional[Tuple[Any, ...]]:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        """
        SELECT username, role, auth_type, is_service_account, keycloak_id
        FROM allowed_users
        WHERE username = ?
        """,
        (username,),
    )
    user = c.fetchone()
    conn.close()
    return user


def add_allowed_user(
    username: str,
    email: str,
    role: str,
    auth_type: str,
    permissions_json: str,
    is_service_account: int = 0,
    full_name: Optional[str] = None,
    keycloak_id: Optional[str] = None,
    password_hash: Optional[bytes] = None,
    must_reset: int = 0,
    db_path: str = DB_PATH,
) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO allowed_users (
            username,
            email,
            added_date,
            role,
            auth_type,
            permissions,
            is_service_account,
            full_name,
            keycloak_id
        )
        VALUES (?, ?, (NOW() + INTERVAL '4 hours'), ?, ?, ?, ?, ?, ?)
        """,
        (username, email, role, auth_type, permissions_json, is_service_account, full_name, keycloak_id),
    )
    conn.commit()
    conn.close()


def upsert_identity_cache(
    username: str,
    email: str,
    role: str,
    auth_type: str,
    permissions_json: str,
    is_service_account: int = 0,
    full_name: Optional[str] = None,
    keycloak_id: Optional[str] = None,
    skip_admin: bool = False,
    db_path: str = DB_PATH,
) -> None:
    if skip_admin and username == ADMIN_USERNAME:
        return
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO allowed_users (
            username,
            email,
            added_date,
            role,
            auth_type,
            permissions,
            is_service_account,
            full_name,
            keycloak_id
        )
        VALUES (?, ?, (NOW() + INTERVAL '4 hours'), ?, ?, ?, ?, ?, ?)
        ON CONFLICT (username) DO UPDATE SET
            email = COALESCE(EXCLUDED.email, allowed_users.email),
            role = EXCLUDED.role,
            auth_type = EXCLUDED.auth_type,
            permissions = EXCLUDED.permissions,
            is_service_account = EXCLUDED.is_service_account,
            full_name = COALESCE(EXCLUDED.full_name, allowed_users.full_name),
            keycloak_id = COALESCE(EXCLUDED.keycloak_id, allowed_users.keycloak_id)
        """,
        (username, email, role, auth_type, permissions_json, is_service_account, full_name, keycloak_id),
    )
    conn.commit()
    conn.close()


def list_identity_cache_rows(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        """
        SELECT username, email, role, auth_type, permissions, is_service_account, full_name, keycloak_id
        FROM allowed_users
        """
    )
    rows = []
    for row in c.fetchall():
        if isinstance(row, dict):
            payload = dict(row)
        else:
            payload = {
                "username": row[0],
                "email": row[1],
                "role": row[2],
                "auth_type": row[3],
                "permissions": row[4],
                "is_service_account": row[5],
                "full_name": row[6],
                "keycloak_id": row[7],
            }
        payload["is_service_account"] = bool(payload.get("is_service_account"))
        rows.append(payload)
    conn.close()
    return rows


def update_user_keycloak_id(username: str, keycloak_id: str, db_path: str = DB_PATH) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("UPDATE allowed_users SET keycloak_id = ? WHERE username = ?", (keycloak_id, username))
    conn.commit()
    conn.close()


def delete_identity(username: str, db_path: str = DB_PATH) -> Tuple[Dict[str, Any], int]:
    conn = get_db_connection(db_path)
    try:
        c = conn.cursor()
        c.execute("SELECT username FROM allowed_users WHERE username = ?", (username,))
        if not c.fetchone():
            return {"error": f"User '{username}' does not exist."}, 404
        c.execute(
            """
            DELETE FROM service_account_api_keys
            WHERE service_account_id = (
                SELECT id FROM allowed_users WHERE username = ?
            )
            """,
            (username,),
        )
        c.execute("DELETE FROM allowed_users WHERE username = ?", (username,))
        conn.commit()
        return {"message": f"User '{username}' deleted successfully."}, 200
    except Exception:
        raise
    finally:
        conn.close()


def update_user_role(username: str, role: str, permissions_json: str, db_path: str = DB_PATH) -> int:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        "UPDATE allowed_users SET role = ?, permissions = ? WHERE username = ?",
        (role, permissions_json, username),
    )
    rowcount = c.rowcount
    if role not in {"pentester", "manager", "admin"}:
        c.execute("DELETE FROM pentest_collaborators WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return rowcount


def find_sso_allowlist(
    username: str,
    email: str = "",
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    needle_user = str(username or "").strip().lower()
    needle_email = str(email or "").strip().lower()
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        row = None
        if needle_user:
            cursor.execute(
                """
                SELECT username, email, role, auth_type, is_service_account, keycloak_id, permissions
                FROM allowed_users
                WHERE username = ?
                """,
                (needle_user,),
            )
            row = cursor.fetchone()
        if not row and needle_email:
            cursor.execute(
                """
                SELECT username, email, role, auth_type, is_service_account, keycloak_id, permissions
                FROM allowed_users
                WHERE lower(email) = ?
                  AND COALESCE(is_service_account, 0) = 0
                ORDER BY username
                LIMIT 1
                """,
                (needle_email,),
            )
            row = cursor.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    if isinstance(row, dict):
        payload = dict(row)
    else:
        payload = {
            "username": row[0],
            "email": row[1],
            "role": row[2],
            "auth_type": row[3],
            "is_service_account": row[4],
            "keycloak_id": row[5],
            "permissions": row[6],
        }
    payload["is_service_account"] = bool(payload.get("is_service_account"))
    payload["username"] = str(payload.get("username") or "").strip().lower()
    payload["email"] = str(payload.get("email") or "").strip()
    payload["role"] = str(payload.get("role") or "user").strip().lower() or "user"
    payload["auth_type"] = str(payload.get("auth_type") or "").strip().lower()
    return payload


def get_user_role(username: str, db_path: str = DB_PATH) -> Optional[str]:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("SELECT role FROM allowed_users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return (row[0] or "user").lower()


def is_service_account_user(username: str, db_path: str = DB_PATH) -> bool:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("SELECT is_service_account FROM allowed_users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    try:
        return bool(row[0])
    except Exception:
        return False


def update_user_permissions(username: str, permissions_json: str, db_path: str = DB_PATH) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        "UPDATE allowed_users SET permissions = ? WHERE username = ?",
        (permissions_json, username),
    )
    conn.commit()
    conn.close()


def remove_user_from_pentest_collaborations(username: str, db_path: str = DB_PATH) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM pentest_collaborators WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def get_display_names(usernames: List[str], db_path: str = DB_PATH) -> Dict[str, str]:
    if not usernames:
        return {}
    conn = get_db_connection(db_path)
    c = conn.cursor()
    placeholders = ", ".join(["?"] * len(usernames))
    c.execute(
        f"SELECT username, full_name FROM allowed_users WHERE username IN ({placeholders})",
        tuple(usernames),
    )
    result = {}
    for row in c.fetchall():
        result[row[0]] = row[1] if row[1] else row[0]
    conn.close()
    for uname in usernames:
        if uname not in result:
            result[uname] = uname
    return result


def get_user_email(username: str, db_path: str = DB_PATH) -> Optional[str]:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("SELECT email FROM allowed_users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        email = row[0]
        return email if email and "@" in str(email) else None
    return None


__all__ = [
    "add_allowed_user",
    "delete_identity",
    "find_sso_allowlist",
    "get_allowed_user_for_login",
    "get_display_names",
    "get_user_email",
    "get_user_role",
    "is_service_account_user",
    "list_identity_cache_rows",
    "remove_user_from_pentest_collaborations",
    "update_user_keycloak_id",
    "update_user_permissions",
    "update_user_role",
    "upsert_identity_cache",
]
