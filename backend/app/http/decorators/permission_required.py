from functools import wraps

from flask import jsonify, session

from app.services.authorization_service import user_has_permission
from app.services.session_policy_service import session_has_expired


def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not session.get("logged_in"):
                return jsonify({"error": "Unauthorized access"}), 403
            if session_has_expired(update_activity=True):
                session.clear()
                return jsonify({"error": "Session expired"}), 401
            role = session.get("user_type")
            username = session.get("username")
            if not role or not username:
                return jsonify({"error": "Unauthorized access"}), 403
            if not user_has_permission(username, role, permission):
                return jsonify({"error": "Unauthorized access"}), 403
            return f(*args, **kwargs)

        return wrapped

    return decorator


__all__ = ["permission_required"]
