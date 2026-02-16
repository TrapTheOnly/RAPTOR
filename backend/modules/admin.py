import os
import bcrypt
import secrets
import sqlite3
import logging
import json
from datetime import datetime
from flask import session, jsonify
from functools import wraps
from modules.session_policy import session_has_expired

logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
if not ADMIN_USERNAME:
    ADMIN_USERNAME = "awadmin"
    logger.warning("ADMIN_USERNAME not set; defaulting to 'awadmin'.")
ADMIN_USERNAME = ADMIN_USERNAME.strip().lower()
os.environ.setdefault("ADMIN_USERNAME", ADMIN_USERNAME)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_PATH, "database.db")

# Basic NIST-aligned password policy (length + block common/compromised patterns)
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 64
COMMON_PASSWORDS = {
    "password", "password1", "123456", "12345678", "123456789",
    "qwerty", "qwerty123", "letmein", "welcome", "admin",
    "admin123", "iloveyou", "monkey", "dragon", "football",
    "abc123", "111111", "trustno1", "sunshine", "princess",
    "login", "qwertyuiop", "passw0rd", "master", "shadow"
}


def _normalize_password_hash(value):
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
    """
    Persist bootstrap admin credentials to a local file with restrictive permissions.
    This avoids writing plaintext credentials into application logs.
    """
    target_path = os.getenv(
        "INITIAL_ADMIN_PASSWORD_FILE",
        os.path.join(DATA_PATH, "initial_admin_credentials.txt")
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
    except Exception as e:
        logger.error(f"Failed to persist initial admin credentials: {e}")
        return None

def validate_password_nist(password, username=None):
    """Validate password against NIST-style requirements."""
    if not password:
        return False, "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    lowered = password.strip().lower()
    if lowered in COMMON_PASSWORDS:
        return False, "Password is too common."
    if username and username.lower() in lowered:
        return False, "Password must not contain the username."
    return True, ""

def init_admin_db():
    """Initializes the admin database with a static admin user."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password BLOB NOT NULL,
                must_reset INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Ensure must_reset column exists for older DBs
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

        static_username, static_password = ADMIN_USERNAME, secrets.token_urlsafe(16)
        hashed_password = bcrypt.hashpw(static_password.encode(), bcrypt.gensalt())
        c.execute("SELECT * FROM admin_users WHERE username = ?", (static_username,))
        if c.fetchone() is None:
            logger.info("no admin")
            c.execute(
                "INSERT INTO admin_users (username, password, must_reset) VALUES (?, ?, 1)",
                (
                    static_username,
                    _prepare_password_for_storage(hashed_password, password_column_type),
                )
            )
            credentials_path = _write_initial_admin_credentials(static_username, static_password)
            if credentials_path:
                logger.warning(
                    "Created admin user '%s'. Initial password stored at '%s'.",
                    static_username,
                    credentials_path
                )
            else:
                logger.warning(
                    "Created admin user '%s'. Initial password could not be stored to file.",
                    static_username
                )
        else:
            logger.info("Admin user already exists. Skipping creation.")
        conn.commit()

def admin_login(username, password):
    """Handles admin login by verifying credentials."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT password FROM admin_users WHERE username = ?", (username,))
            result = c.fetchone()
            existing_hash = _normalize_password_hash(result[0]) if result else None
            if existing_hash and bcrypt.checkpw(password.encode(), existing_hash):
                return True
            return False
    except Exception as e:
        print(e)
        logger.error(f"Error authenticating admin user: {e}")
        return False

def admin_requires_password_reset(username):
    """Returns True if the admin account must reset password."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT must_reset FROM admin_users WHERE username = ?", (username,))
            result = c.fetchone()
            return bool(result and result[0] == 1)
    except Exception as e:
        logger.error(f"Error checking password reset flag: {e}")
        return False

def check_current_admin_password(current_password):
    """Verifies the current admin password."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT password FROM admin_users WHERE username = ?", (ADMIN_USERNAME,))
            result = c.fetchone()
            existing_hash = _normalize_password_hash(result[0]) if result else None
            return bool(existing_hash and bcrypt.checkpw(current_password.encode(), existing_hash))
    except Exception as e:
        logger.error(f"Error verifying current password: {e}")
        return False

def change_admin_password(current_password, new_password):
    """Changes the admin password after verifying the current password."""
    if not check_current_admin_password(current_password):
        return {"error": "Current password is incorrect."}, 401
    ok, msg = validate_password_nist(new_password, username=ADMIN_USERNAME)
    if not ok:
        return {"error": msg}, 400
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT password FROM admin_users WHERE username = ?", (ADMIN_USERNAME,))
            result = c.fetchone()
            if not result:
                return {"error": "Admin user not found."}, 404
            existing_hash = _normalize_password_hash(result[0])
            if existing_hash and bcrypt.checkpw(new_password.encode(), existing_hash):
                return {"error": "New password must be different from the current password."}, 400
            hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
            password_column_type = _admin_password_column_type(c)
            c.execute(
                "UPDATE admin_users SET password = ?, must_reset = 0 WHERE username = ?",
                (
                    _prepare_password_for_storage(hashed_password, password_column_type),
                    ADMIN_USERNAME,
                )
            )
            conn.commit()
        return {"message": "Password changed successfully."}, 200
    except Exception as e:
        logger.error(f"Error changing admin password: {e}")
        return {"error": "Failed to change password."}, 500

def reset_admin_password(new_password):
    """Resets the admin password without requiring the current password."""
    ok, msg = validate_password_nist(new_password, username=ADMIN_USERNAME)
    if not ok:
        return {"error": msg}, 400
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT password FROM admin_users WHERE username = ?", (ADMIN_USERNAME,))
            result = c.fetchone()
            if not result:
                return {"error": "Admin user not found."}, 404
            existing_hash = _normalize_password_hash(result[0])
            if existing_hash and bcrypt.checkpw(new_password.encode(), existing_hash):
                return {"error": "New password must be different from the temporary password."}, 400
            hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
            password_column_type = _admin_password_column_type(c)
            c.execute(
                "UPDATE admin_users SET password = ?, must_reset = 0 WHERE username = ?",
                (
                    _prepare_password_for_storage(hashed_password, password_column_type),
                    ADMIN_USERNAME,
                )
            )
            if c.rowcount == 0:
                return {"error": "Admin user not found."}, 404
            conn.commit()
        return {"message": "Password reset successfully."}, 200
    except Exception as e:
        logger.error(f"Error resetting admin password: {e}")
        return {"error": "Failed to reset password."}, 500

def get_existing_users():
    """Retrieves all users in the allowed_users table."""
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
    except Exception as e:
        logger.error(f"Error retrieving existing users: {e}")
        return {"error": "Failed to fetch existing users."}, 500

def delete_user(username):
    """Deletes a user from the allowed_users table."""
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
    except Exception as e:
        logger.error(f"Error deleting user '{username}': {e}")
        return {"error": f"Failed to delete user '{username}'."}, 500

def admin_required(f):
    """Decorator to protect admin-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session_has_expired(update_activity=True):
            session.clear()
            return jsonify({"error": "Session expired"}), 401
        if (
            not session.get('logged_in')
            or session.get('user_type') != 'admin'
            or session.get('reset_required')
        ):
            return jsonify({"error": "Unauthorized access"}), 403
        return f(*args, **kwargs)
    return decorated_function

def admin_or_manager_required(f):
    """Decorator to protect admin- or manager-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session_has_expired(update_activity=True):
            session.clear()
            return jsonify({"error": "Session expired"}), 401
        if (
            not session.get('logged_in')
            or session.get('user_type') not in ('admin', 'manager')
            or session.get('reset_required')
        ):
            return jsonify({"error": "Unauthorized access"}), 403
        return f(*args, **kwargs)
    return decorated_function

# 
