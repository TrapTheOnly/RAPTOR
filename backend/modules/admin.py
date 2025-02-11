import os
import bcrypt
import secrets
import sqlite3
import logging
from flask import session, jsonify

# Configure logging
logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
DB_PATH = os.getenv("DATA_PATH") + "database.db"

def init_admin_db():
    """
    Initializes the admin database with a static admin user.
    The admin user credentials are generated and logged once.
    """
    
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        """)

        static_username = ADMIN_USERNAME
        static_password = secrets.token_urlsafe(16)
        hashed_password = bcrypt.hashpw(static_password.encode(), bcrypt.gensalt())

        c.execute("SELECT * FROM admin_users WHERE username = ?", (static_username,))
        if c.fetchone() is None:
            c.execute("INSERT INTO admin_users (username, password) VALUES (?, ?)", (static_username, hashed_password))
            with open("/tmp/writehere.txt", "a") as file:
                file.write(f"Admin user created! Username: {static_username}, Password: {static_password}")
            logger.info(f"Admin user created! Username: {static_username}, Password: {static_password}")
        else:
            logger.info("Admin user already exists. Skipping creation.")

        conn.commit()
        conn.close()

def admin_login(username, password):
    """
    Handles admin login by verifying credentials.
    Returns True if authentication succeeds, otherwise False.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT password FROM admin_users WHERE username = ?", (username,))
        result = c.fetchone()
        conn.close()

        if result and bcrypt.checkpw(password.encode(), result[0]):
            session['admin_logged_in'] = True
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error authenticating admin user: {e}")
        return False
    
def check_current_admin_password(current_password):
    """
    Verifies the current admin password.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT password FROM admin_users WHERE username = ?", (ADMIN_USERNAME,))
        result = c.fetchone()
        conn.close()

        if result and bcrypt.checkpw(current_password.encode(), result[0]):
            return True
        return False
    except Exception as e:
        logger.error(f"Error verifying current password: {e}")
        return False

def change_admin_password(current_password, new_password):
    """
    Changes the admin password after verifying the current password.
    """
    if not check_current_admin_password(current_password):
        return {"error": "Current password is incorrect."}, 401

    try:
        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            UPDATE admin_users
            SET password = ?
            WHERE username = ?
        """, (hashed_password, ADMIN_USERNAME))
        conn.commit()
        conn.close()

        return {"message": "Password changed successfully."}, 200
    except Exception as e:
        logger.error(f"Error changing admin password: {e}")
        return {"error": "Failed to change password."}, 500

def get_existing_users():
    """
    Retrieves all users in the allowed_users table.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT username, email, added_date, role FROM allowed_users")
        rows = c.fetchall()
        conn.close()

        users = [dict(row) for row in rows]
        return {"users": users}, 200
    except Exception as e:
        logger.error(f"Error retrieving existing users: {e}")
        return {"error": "Failed to fetch existing users."}, 500
    
def delete_user(username):
    """
    Deletes a user from the allowed_users table.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if the user exists
        c.execute("SELECT username FROM allowed_users WHERE username = ?", (username,))
        if not c.fetchone():
            conn.close()
            return {"error": f"User '{username}' does not exist."}, 404

        # Delete the user
        c.execute("DELETE FROM allowed_users WHERE username = ?", (username,))
        conn.commit()
        conn.close()

        logger.info(f"User '{username}' deleted successfully.")
        return {"message": f"User '{username}' deleted successfully."}, 200
    except Exception as e:
        logger.error(f"Error deleting user '{username}': {e}")
        return {"error": f"Failed to delete user '{username}'."}, 500

def admin_required(f):
    """
    Decorator to protect admin-only routes.
    """
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({"error": "Unauthorized access"}), 403
        return f(*args, **kwargs)

    return decorated_function