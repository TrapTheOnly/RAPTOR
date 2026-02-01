import os
import bcrypt
import secrets
import sqlite3
import logging
from flask import session, jsonify
from functools import wraps

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
    if os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    must_reset INTEGER NOT NULL DEFAULT 0
                )
            """)
            # Ensure must_reset column exists for older DBs
            c.execute("PRAGMA table_info(admin_users)")
            columns = {row[1] for row in c.fetchall()}
            if "must_reset" not in columns:
                c.execute("ALTER TABLE admin_users ADD COLUMN must_reset INTEGER NOT NULL DEFAULT 0")

            static_username, static_password = ADMIN_USERNAME, secrets.token_urlsafe(16)
            hashed_password = bcrypt.hashpw(static_password.encode(), bcrypt.gensalt())
            c.execute("SELECT * FROM admin_users WHERE username = ?", (static_username,))
            if c.fetchone() is None:
                logger.info("no admin")
                c.execute(
                    "INSERT INTO admin_users (username, password, must_reset) VALUES (?, ?, 1)",
                    (static_username, hashed_password)
                )
                logger.info("Created admin user with username: %s and password: %s", static_username, static_password)
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
            if result and bcrypt.checkpw(password.encode(), result[0]):
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
            return bool(result and bcrypt.checkpw(current_password.encode(), result[0]))
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
            if bcrypt.checkpw(new_password.encode(), result[0]):
                return {"error": "New password must be different from the current password."}, 400
            hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
            c.execute(
                "UPDATE admin_users SET password = ?, must_reset = 0 WHERE username = ?",
                (hashed_password, ADMIN_USERNAME)
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
            if bcrypt.checkpw(new_password.encode(), result[0]):
                return {"error": "New password must be different from the temporary password."}, 400
            hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
            c.execute(
                "UPDATE admin_users SET password = ?, must_reset = 0 WHERE username = ?",
                (hashed_password, ADMIN_USERNAME)
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
            c.execute("SELECT username, email, added_date, role, auth_type FROM allowed_users")
            return {"users": [dict(row) for row in c.fetchall()]}, 200
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
        if (
            not session.get('logged_in')
            or session.get('user_type') not in ('admin', 'manager')
            or session.get('reset_required')
        ):
            return jsonify({"error": "Unauthorized access"}), 403
        return f(*args, **kwargs)
    return decorated_function

# 
