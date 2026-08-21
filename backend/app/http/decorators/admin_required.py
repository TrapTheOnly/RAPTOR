from functools import wraps

from flask import jsonify, session

from app.services.session_policy_service import session_has_expired
from app.services.sso_auth_service import drop_invalid_identity_session


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if drop_invalid_identity_session(session):
            return jsonify({"error": "Session expired"}), 401
        if session_has_expired(update_activity=True):
            session.clear()
            return jsonify({"error": "Session expired"}), 401
        if (
            not session.get("logged_in")
            or session.get("user_type") != "admin"
            or session.get("reset_required")
        ):
            return jsonify({"error": "Unauthorized access"}), 403
        return f(*args, **kwargs)

    return decorated_function


def admin_or_manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if drop_invalid_identity_session(session):
            return jsonify({"error": "Session expired"}), 401
        if session_has_expired(update_activity=True):
            session.clear()
            return jsonify({"error": "Session expired"}), 401
        if (
            not session.get("logged_in")
            or session.get("user_type") not in ("admin", "manager")
            or session.get("reset_required")
        ):
            return jsonify({"error": "Unauthorized access"}), 403
        return f(*args, **kwargs)

    return decorated_function


__all__ = ["admin_or_manager_required", "admin_required"]
