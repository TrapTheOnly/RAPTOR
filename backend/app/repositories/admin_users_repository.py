import json
import logging
import os
import sqlite3
from datetime import datetime

import bcrypt

from app.config import DB_PATH

logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
if not ADMIN_USERNAME:
    ADMIN_USERNAME = "awadmin"
    logger.warning("ADMIN_USERNAME not set; defaulting to 'awadmin'.")
ADMIN_USERNAME = ADMIN_USERNAME.strip().lower()
os.environ.setdefault("ADMIN_USERNAME", ADMIN_USERNAME)


def normalize_password_hash(value):
    if value is None:
        return None
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    try:
        return bytes(value)
    except Exception:
        return None


def _admin_password_column_type(cursor):
    cursor.execute("PRAGMA table_info(admin_users)")
    rows = cursor.fetchall()
    for row in rows:
        if str(row[1]).strip().lower() == "password":
            return str(row[2] or "").strip().lower()
    return ""


def _prepare_password_for_storage(password_hash, column_type):
    if not password_hash:
        return password_hash
    if "text" in (column_type or ""):
        return password_hash.decode("utf-8")
    return password_hash


def _write_initial_admin_credentials(username, password):
    target_path = os.getenv(
        "INITIAL_ADMIN_PASSWORD_FILE",
        os.path.join(os.path.dirname(DB_PATH), "initial_admin_credentials.txt"),
    )
    try:
        absolute_target = os.path.abspath(target_path)
        target_dir = os.path.dirname(absolute_target)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        payload = (
            "RAPTOR initial admin credentials\n"
            f"generated_at_utc={datetime.utcnow().isoformat()}Z\n"
            f"username={username}\n"
            f"password={password}\n"
            "warning=Delete this file immediately after first successful admin login.\n"
        )
        fd = os.open(absolute_target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        try:
            os.chmod(absolute_target, 0o600)
        except Exception:
            pass
        return absolute_target
    except Exception as exc:
        logger.error(f"Failed to persist initial admin credentials: {exc}")
        return None


def ensure_admin_user_exists():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password BLOB NOT NULL,
                must_reset INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        c.execute("PRAGMA table_info(admin_users)")
        pragma_rows = c.fetchall()
        columns = {row[1] for row in pragma_rows}
        password_column_type = ""
        for row in pragma_rows:
            if str(row[1]).strip().lower() == "password":
                password_column_type = str(row[2] or "").strip().lower()
                break
        if "must_reset" not in columns:
            c.execute("ALTER TABLE admin_users ADD COLUMN must_reset INTEGER NOT NULL DEFAULT 0")

        static_password = secrets_token()
        hashed_password = bcrypt.hashpw(static_password.encode(), bcrypt.gensalt())
        c.execute("SELECT * FROM admin_users WHERE username = ?", (ADMIN_USERNAME,))
        if c.fetchone() is None:
            c.execute(
                "INSERT INTO admin_users (username, password, must_reset) VALUES (?, ?, 1)",
                (ADMIN_USERNAME, _prepare_password_for_storage(hashed_password, password_column_type)),
            )
            credentials_path = _write_initial_admin_credentials(ADMIN_USERNAME, static_password)
            if credentials_path:
                logger.warning(
                    "Created admin user '%s'. Initial password stored at '%s'.",
                    ADMIN_USERNAME,
                    credentials_path,
                )
            else:
                logger.warning(
                    "Created admin user '%s'. Initial password could not be stored to file.",
                    ADMIN_USERNAME,
                )
        else:
            logger.info("Admin user already exists. Skipping creation.")
        conn.commit()


def secrets_token():
    import secrets

    return secrets.token_urlsafe(16)


def admin_login(username, password):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT password FROM admin_users WHERE username = ?", (username,))
            result = c.fetchone()
            existing_hash = normalize_password_hash(result[0]) if result else None
            return bool(existing_hash and bcrypt.checkpw(password.encode(), existing_hash))
    except Exception as exc:
        logger.error(f"Error authenticating admin user: {exc}")
        return False


def admin_requires_password_reset(username):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT must_reset FROM admin_users WHERE username = ?", (username,))
            result = c.fetchone()
            return bool(result and result[0] == 1)
    except Exception as exc:
        logger.error(f"Error checking password reset flag: {exc}")
        return False


def check_current_admin_password(current_password):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT password FROM admin_users WHERE username = ?", (ADMIN_USERNAME,))
            result = c.fetchone()
            existing_hash = normalize_password_hash(result[0]) if result else None
            return bool(existing_hash and bcrypt.checkpw(current_password.encode(), existing_hash))
    except Exception as exc:
        logger.error(f"Error verifying current password: {exc}")
        return False


def update_admin_password(new_password):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT password FROM admin_users WHERE username = ?", (ADMIN_USERNAME,))
        result = c.fetchone()
        if not result:
            return "not_found"
        existing_hash = normalize_password_hash(result[0])
        if existing_hash and bcrypt.checkpw(new_password.encode(), existing_hash):
            return "same_password"

        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
        password_column_type = _admin_password_column_type(c)
        c.execute(
            "UPDATE admin_users SET password = ?, must_reset = 0 WHERE username = ?",
            (_prepare_password_for_storage(hashed_password, password_column_type), ADMIN_USERNAME),
        )
        if c.rowcount == 0:
            return "not_found"
        conn.commit()
    return "updated"


def get_existing_users():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT username, email, added_date, role, auth_type, permissions FROM allowed_users")
            users = []
            for row in c.fetchall():
                user = dict(row)
                raw_permissions = user.get("permissions")
                if raw_permissions:
                    try:
                        user["permissions"] = json.loads(raw_permissions)
                    except json.JSONDecodeError:
                        user["permissions"] = []
                else:
                    user["permissions"] = []
                users.append(user)
            return {"users": users}, 200
    except Exception as exc:
        logger.error(f"Error retrieving existing users: {exc}")
        return {"error": "Failed to fetch existing users."}, 500


def delete_user(username):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT username FROM allowed_users WHERE username = ?", (username,))
            if not c.fetchone():
                return {"error": f"User '{username}' does not exist."}, 404
            c.execute("DELETE FROM allowed_users WHERE username = ?", (username,))
            conn.commit()
        logger.info(f"User '{username}' deleted successfully.")
        return {"message": f"User '{username}' deleted successfully."}, 200
    except Exception as exc:
        logger.error(f"Error deleting user '{username}': {exc}")
        return {"error": f"Failed to delete user '{username}'."}, 500


__all__ = [
    "ADMIN_USERNAME",
    "admin_login",
    "admin_requires_password_reset",
    "check_current_admin_password",
    "delete_user",
    "ensure_admin_user_exists",
    "get_existing_users",
    "normalize_password_hash",
    "update_admin_password",
]
