from typing import Any, Dict, List, Optional, Tuple

from app.config import DB_PATH
from app.integrations.db.connection import get_db_connection


def get_allowed_user_for_login(username: str, db_path: str = DB_PATH) -> Optional[Tuple[Any, ...]]:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        """
        SELECT username, role, auth_type, password, must_reset, is_service_account
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
    password_hash: Optional[bytes],
    must_reset: int,
    permissions_json: str,
    is_service_account: int = 0,
    full_name: Optional[str] = None,
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
            password,
            must_reset,
            permissions,
            is_service_account,
            full_name
        )
        VALUES (?, ?, (NOW() + INTERVAL '4 hours'), ?, ?, ?, ?, ?, ?, ?)
        """,
        (username, email, role, auth_type, password_hash, must_reset, permissions_json, is_service_account, full_name),
    )
    conn.commit()
    conn.close()


def get_user_password(username: str, db_path: str = DB_PATH) -> Optional[Any]:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("SELECT password FROM allowed_users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return row[0]


def update_local_user_password(username: str, hashed_password: bytes, db_path: str = DB_PATH) -> int:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        "UPDATE allowed_users SET password = ?, must_reset = 0, auth_type = 'local' WHERE username = ?",
        (hashed_password, username),
    )
    rowcount = c.rowcount
    conn.commit()
    conn.close()
    return rowcount


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


__all__ = [
    "add_allowed_user",
    "get_allowed_user_for_login",
    "get_display_names",
    "get_user_password",
    "get_user_role",
    "is_service_account_user",
    "remove_user_from_pentest_collaborations",
    "update_local_user_password",
    "update_user_permissions",
    "update_user_role",
]
