import logging
from typing import Any, Dict, Optional, Tuple

import bcrypt

from app.http.request_utils import normalize_auth_key, normalize_password_hash
from app.repositories.auth_lockout_repository import (
    clear_login_lockout_state,
    get_login_lockout_status,
    register_failed_login_attempt,
)
from app.repositories.users_repository import (
    get_allowed_user_for_login,
    get_user_password,
    update_local_user_password,
)
from app.services.admin_auth_service import (
    ADMIN_USERNAME,
    admin_login,
    admin_requires_password_reset,
    reset_admin_password,
    validate_password_nist,
)
from app.services.authorization_service import get_user_permissions
from app.services.session_policy_service import (
    extend_session,
    get_session_timing,
    initialize_session_tracking,
    session_has_expired,
)
from app.integrations.ldap.client import ldap_authenticate

logger = logging.getLogger(__name__)


def _invalid_credentials_response(username: str) -> Tuple[Dict[str, Any], int]:
    lockout = register_failed_login_attempt(username)
    if lockout.get("locked"):
        return {
            "error": "Too many failed login attempts. Try again later.",
            "retry_after_seconds": int(lockout.get("retry_after_seconds") or 0),
        }, 429
    return {"error": "Invalid credentials"}, 401


def login(data: Dict[str, Any], session_obj: Any) -> Tuple[Dict[str, Any], int]:
    if not data:
        return {"error": "No data provided"}, 400

    username = normalize_auth_key(data.get("username"))
    password = data.get("password")

    if not username or not password:
        return {"error": "Username and password required"}, 400

    lockout = get_login_lockout_status(username)
    if lockout.get("locked"):
        return {
            "error": "Too many failed login attempts. Try again later.",
            "retry_after_seconds": int(lockout.get("retry_after_seconds") or 0),
        }, 429

    user = get_allowed_user_for_login(username)

    if username == ADMIN_USERNAME:
        if admin_login(username, password):
            clear_login_lockout_state(username)
            session_obj.permanent = True
            session_obj["username"] = username
            session_obj["user_type"] = "admin"

            if admin_requires_password_reset(username):
                session_obj["reset_required"] = True
                session_obj["logged_in"] = False
                return {
                    "status": "password_reset_required",
                    "username": username,
                    "user_type": "admin",
                    "permissions": list(get_user_permissions(username, "admin")),
                }, 200

            session_obj["logged_in"] = True
            session_obj.pop("reset_required", None)
            initialize_session_tracking()
            return {
                "status": "logged_in",
                "username": username,
                "user_type": "admin",
                "permissions": list(get_user_permissions(username, "admin")),
            }, 200
        return _invalid_credentials_response(username)

    if user:
        user_role = user[1] if user[1] else "user"
        auth_type = user[2] if user[2] else "ldap"
        password_hash = normalize_password_hash(user[3])
        must_reset = bool(user[4])

        if auth_type == "local":
            if not password_hash or not bcrypt.checkpw(password.encode(), password_hash):
                return _invalid_credentials_response(username)

            clear_login_lockout_state(username)
            session_obj.permanent = True
            session_obj["username"] = user[0]
            session_obj["user_type"] = user_role

            if must_reset:
                session_obj["reset_required"] = True
                session_obj["logged_in"] = False
                return {
                    "status": "password_reset_required",
                    "username": username,
                    "user_type": user_role,
                    "permissions": list(get_user_permissions(username, user_role)),
                }, 200

            session_obj["logged_in"] = True
            session_obj.pop("reset_required", None)
            initialize_session_tracking()
            return {
                "status": "logged_in",
                "username": username,
                "user_type": user_role,
                "permissions": list(get_user_permissions(username, user_role)),
            }, 200

        if ldap_authenticate(username, password):
            clear_login_lockout_state(username)
            session_obj.permanent = True
            session_obj["logged_in"] = True
            session_obj["username"] = user[0]
            session_obj["user_type"] = user_role
            session_obj.pop("reset_required", None)
            initialize_session_tracking()
            return {
                "status": "logged_in",
                "username": username,
                "user_type": session_obj["user_type"],
                "permissions": list(get_user_permissions(username, user_role)),
            }, 200

        return _invalid_credentials_response(username)

    return _invalid_credentials_response(username)


def session_status(session_obj: Any) -> Tuple[Dict[str, Any], int]:
    if session_obj.get("logged_in") and session_has_expired(update_activity=False):
        session_obj.clear()
        return {"status": "logged_out"}, 401

    if session_obj.get("reset_required"):
        return {
            "status": "password_reset_required",
            "username": session_obj.get("username"),
            "user_type": session_obj.get("user_type"),
            "permissions": list(
                get_user_permissions(session_obj.get("username"), session_obj.get("user_type"))
            ),
        }, 200

    if "logged_in" in session_obj and session_obj["logged_in"]:
        user_type = session_obj.get("user_type")
        timing = get_session_timing(update_activity=False) or {}
        return {
            "status": "logged_in",
            "username": session_obj.get("username"),
            "user_type": user_type,
            "permissions": list(get_user_permissions(session_obj.get("username"), user_type)),
            "session_remaining_seconds": timing.get("remaining_seconds"),
            "active_remaining_seconds": timing.get("active_remaining_seconds"),
            "idle_remaining_seconds": timing.get("idle_remaining_seconds"),
        }, 200

    return {"status": "logged_out"}, 401


def extend_logged_in_session(session_obj: Any) -> Tuple[Dict[str, Any], int]:
    if not session_obj.get("logged_in"):
        return {"status": "logged_out"}, 401
    if session_has_expired(update_activity=False):
        session_obj.clear()
        return {"status": "logged_out"}, 401

    timing = extend_session()
    if not timing:
        return {"status": "logged_out"}, 401

    user_type = session_obj.get("user_type")
    return {
        "status": "logged_in",
        "username": session_obj.get("username"),
        "user_type": user_type,
        "permissions": list(get_user_permissions(session_obj.get("username"), user_type)),
        "session_remaining_seconds": timing.get("remaining_seconds"),
        "active_remaining_seconds": timing.get("active_remaining_seconds"),
        "idle_remaining_seconds": timing.get("idle_remaining_seconds"),
    }, 200


def logout(session_obj: Any) -> Tuple[Dict[str, Any], int]:
    session_obj.clear()
    return {"status": "logged_out"}, 200


def admin_reset_password(data: Dict[str, Any], session_obj: Any) -> Tuple[Dict[str, Any], int]:
    if not session_obj.get("reset_required") or session_obj.get("username") != ADMIN_USERNAME:
        return {"error": "Unauthorized"}, 403

    if not data:
        return {"error": "No data provided"}, 400
    new_password = data.get("new_password")

    if not new_password:
        return {"error": "New password is required."}, 400

    response, status_code = reset_admin_password(new_password)
    if status_code == 200:
        session_obj["logged_in"] = True
        session_obj["reset_required"] = False
        session_obj["user_type"] = "admin"
        return {
            "status": "logged_in",
            "username": session_obj.get("username"),
            "user_type": "admin",
            "permissions": list(get_user_permissions(session_obj.get("username"), "admin")),
        }, 200

    return response, status_code


def user_reset_password(data: Dict[str, Any], session_obj: Any) -> Tuple[Dict[str, Any], int]:
    if not session_obj.get("reset_required") or session_obj.get("user_type") == "admin":
        return {"error": "Unauthorized"}, 403

    if not data:
        return {"error": "No data provided"}, 400
    new_password = data.get("new_password")

    if not new_password:
        return {"error": "New password is required."}, 400

    username = session_obj.get("username")
    ok, msg = validate_password_nist(new_password, username=username)
    if not ok:
        return {"error": msg}, 400

    try:
        existing_value = get_user_password(username)
        if not existing_value:
            return {"error": "User not found."}, 404

        existing_hash = normalize_password_hash(existing_value)
        if existing_hash and bcrypt.checkpw(new_password.encode(), existing_hash):
            return {
                "error": "New password must be different from the temporary password."
            }, 400

        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
        rowcount = update_local_user_password(username, hashed_password)
        if rowcount == 0:
            return {"error": "User not found."}, 404

        session_obj["logged_in"] = True
        session_obj["reset_required"] = False
        user_type = session_obj.get("user_type")
        return {
            "status": "logged_in",
            "username": username,
            "user_type": user_type,
            "permissions": list(get_user_permissions(username, user_type)),
        }, 200
    except Exception as e:
        logger.error(f"Error resetting password for user {username}: {e}")
        return {"error": "Failed to reset password."}, 500
