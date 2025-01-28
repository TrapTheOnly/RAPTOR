import os
import bcrypt
import secrets
import sqlite3
from flask import session, jsonify

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
            print(f"Admin user created! Username: {static_username}, Password: {static_password}")
        else:
            print("Admin user already exists. Skipping creation.")

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
        print(f"Error authenticating admin user: {e}")
        return False

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