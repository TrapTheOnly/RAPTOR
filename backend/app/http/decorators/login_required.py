import logging
from functools import wraps

from flask import jsonify, redirect, session

from app.services.session_policy_service import session_has_expired

logger = logging.getLogger(__name__)


def login_required_json(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            logger.warning("Unauthorized access attempt to JSON route")
            return jsonify({"error": "Unauthorized"}), 403
        if session_has_expired(update_activity=True):
            session.clear()
            return jsonify({"error": "Session expired"}), 401
        return f(*args, **kwargs)

    return wrapper


def login_required_html(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            logger.warning("Unauthorized access attempt to HTML route")
            return redirect("/login")
        if session_has_expired(update_activity=True):
            session.clear()
            return redirect("/login")
        return f(*args, **kwargs)

    return wrapper


__all__ = ["login_required_html", "login_required_json"]
