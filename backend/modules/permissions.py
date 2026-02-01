import os
import json
import sqlite3
import logging
from functools import wraps
from flask import session, jsonify

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_PATH, "database.db")

PERMISSIONS = {
    "view_records",
    "view_security_dashboard",
    "modify_records",
    "view_record_details",
    "export_records",
    "manage_apps",
    "view_pentest_page",
    "modify_pentests",
    "export_pentests",
    "reassign_pentests_admin",
    "delete_records",
    "modify_others_pentests_admin"
}

ROLE_DEFAULTS = {
    "user": {
        "view_records",
        "modify_records",
        "view_record_details",
        "export_records"
    },
    "pentester": {
        "view_records",
        "view_security_dashboard",
        "view_record_details",
        "export_records",
        "view_pentest_page",
        "modify_pentests",
        "export_pentests"
    },
    "manager": {
        "view_records",
        "view_security_dashboard",
        "modify_records",
        "view_record_details",
        "export_records",
        "manage_apps",
        "view_pentest_page",
        "modify_pentests",
        "export_pentests",
        "reassign_pentests_admin",
        "delete_records",
        "modify_others_pentests_admin"
    },
    "admin": set(PERMISSIONS)
}

ROLE_OPTIONAL = {
    "user": {"view_security_dashboard", "manage_apps"},
    "pentester": {"modify_records", "manage_apps"},
    "manager": set(),
    "admin": set()
}

def sanitize_extra_permissions(role, extra_permissions):
    allowed = ROLE_OPTIONAL.get(role, set())
    if not extra_permissions:
        return []
    return sorted({perm for perm in extra_permissions if perm in allowed})

def get_effective_permissions(role, extra_permissions=None):
    if role == "admin":
        return set(PERMISSIONS)
    base = set(ROLE_DEFAULTS.get(role, set()))
    extras = set(extra_permissions or [])
    extras = {perm for perm in extras if perm in ROLE_OPTIONAL.get(role, set())}
    return base | extras

def _load_permissions_from_db(username):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT permissions FROM allowed_users WHERE username = ?", (username,))
            row = c.fetchone()
            if not row or not row[0]:
                return []
            try:
                value = json.loads(row[0])
                if isinstance(value, list):
                    return [perm for perm in value if perm in PERMISSIONS]
            except json.JSONDecodeError:
                return []
    except Exception as e:
        logger.error(f"Error loading permissions for {username}: {e}")
    return []

def get_user_permissions(username, role):
    extras = _load_permissions_from_db(username)
    return get_effective_permissions(role, extras)

def user_has_permission(username, role, permission):
    if permission not in PERMISSIONS:
        return False
    return permission in get_user_permissions(username, role)

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not session.get("logged_in"):
                return jsonify({"error": "Unauthorized access"}), 403
            role = session.get("user_type")
            username = session.get("username")
            if not role or not username:
                return jsonify({"error": "Unauthorized access"}), 403
            if not user_has_permission(username, role, permission):
                return jsonify({"error": "Unauthorized access"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator
