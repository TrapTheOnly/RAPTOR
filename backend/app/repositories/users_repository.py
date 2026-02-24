from typing import Any, Optional, Tuple

from app.config import DB_PATH
from app.integrations.db.connection import get_db_connection


def get_allowed_user_for_login(username: str, db_path: str = DB_PATH) -> Optional[Tuple[Any, ...]]:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT username, role, auth_type, password, must_reset FROM allowed_users WHERE username = ?",
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
    db_path: str = DB_PATH,
) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO allowed_users (username, email, added_date, role, auth_type, password, must_reset, permissions)
        VALUES (?, ?, (NOW() + INTERVAL '4 hours'), ?, ?, ?, ?, ?)
        """,
        (username, email, role, auth_type, password_hash, must_reset, permissions_json),
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


def update_user_permissions(username: str, permissions_json: str, db_path: str = DB_PATH) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute(
        "UPDATE allowed_users SET permissions = ? WHERE username = ?",
        (permissions_json, username),
    )
    conn.commit()
    conn.close()
