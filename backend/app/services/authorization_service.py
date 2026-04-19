import json
import logging

from app.config import DB_PATH
from app.domain.auth.permissions import PERMISSIONS, get_effective_permissions
from app.integrations.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def _load_permissions_from_db(username):
    try:
        with get_db_connection(DB_PATH) as conn:
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
    except Exception as exc:
        logger.error(f"Error loading permissions for {username}: {exc}")
    return []


def get_user_permissions(username, role):
    extras = _load_permissions_from_db(username)
    return get_effective_permissions(role, extras)


def user_has_permission(username, role, permission):
    if permission not in PERMISSIONS:
        return False
    return permission in get_user_permissions(username, role)


__all__ = ["get_user_permissions", "user_has_permission"]
