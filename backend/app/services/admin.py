import os
import bcrypt
import secrets
import sqlite3
import logging
import stat
from pathlib import Path
from functools import wraps
from flask import session, jsonify
from ..config import DB_PATH

logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_CREDENTIALS_FILE = os.getenv("ADMIN_CREDENTIALS_FILE", "/tmp/writehere.txt")


def init_admin_db():
    """Initializes the admin database with a static admin user."""
    if os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL
                )
            """
            )
            static_username, static_password = ADMIN_USERNAME, secrets.token_urlsafe(16)
            hashed_password = bcrypt.hashpw(static_password.encode(), bcrypt.gensalt())
            c.execute("SELECT * FROM admin_users WHERE username = ?", (static_username,))
            if c.fetchone() is None:
                logger.info("no admin")
                c.execute(
                    "INSERT INTO admin_users (username, password) VALUES (?, ?)",
                    (static_username, hashed_password),
                )

                try:
                    credentials_path = Path(ADMIN_CREDENTIALS_FILE).expanduser()
                    credentials_path.parent.mkdir(parents=True, exist_ok=True)
                    credentials_path.write_text(
                        f"Username: {static_username}\nPassword: {static_password}\n",
                        encoding="utf-8",
                    )
                    credentials_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
                    logger.info(
                        "Created admin user with username: %s. Credentials written to %s",
                        static_username,
                        credentials_path,
                    )
                except Exception as write_err:
                    logger.error(
                        "Created admin user with username: %s, but failed to write credentials to %s: %s",
                        static_username,
                        ADMIN_CREDENTIALS_FILE,
                        write_err,
                    )
                    logger.info("Admin password for this session: %s", static_password)
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
        logger.error("Error authenticating admin user: %s", e)
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
        logger.error("Error verifying current password: %s", e)
        return False


def change_admin_password(current_password, new_password):
    """Changes the admin password after verifying the current password."""
    if not check_current_admin_password(current_password):
        return {"error": "Current password is incorrect."}, 401
    try:
        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE admin_users SET password = ? WHERE username = ?",
                (hashed_password, ADMIN_USERNAME),
            )
            conn.commit()
        return {"message": "Password changed successfully."}, 200
    except Exception as e:
        logger.error("Error changing admin password: %s", e)
        return {"error": "Failed to change password."}, 500


def get_existing_users():
    """Retrieves all users in the allowed_users table."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT username, email, added_date, role FROM allowed_users")
            return {"users": [dict(row) for row in c.fetchall()]}, 200
    except Exception as e:
        logger.error("Error retrieving existing users: %s", e)
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
        logger.info("User '%s' deleted successfully.", username)
        return {"message": f"User '{username}' deleted successfully."}, 200
    except Exception as e:
        logger.error("Error deleting user '%s': %s", username, e)
        return {"error": f"Failed to delete user '{username}'."}, 500


def admin_required(f):
    """Decorator to protect admin-only routes."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_type") == "admin":
            return jsonify({"error": "Unauthorized access"}), 403
        return f(*args, **kwargs)

    return decorated_function
