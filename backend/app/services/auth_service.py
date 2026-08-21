import logging
from typing import Any, Dict, Tuple

from app.http.request_utils import normalize_auth_key
from app.integrations.keycloak.client import password_grant
from app.integrations.keycloak.constants import ACCESS_ROLE, role_from_realm_roles
from app.repositories.users_repository import get_allowed_user_for_login
from app.services.admin_auth_service import (
    ADMIN_USERNAME,
    reset_admin_password,
    validate_password_nist,
)
from app.services.authorization_service import get_user_permissions
from app.services.keycloak_identity_service import (
    auth_type_for_username,
    cache_from_login,
    prepare_user_for_raptor_login,
    set_user_password,
    user_has_required_action,
)
from app.services.session_policy_service import (
    extend_session,
    get_session_timing,
    initialize_session_tracking,
    session_has_expired,
)

logger = logging.getLogger(__name__)


def _audit_login(username: str) -> None:
    from app.services.audit_service import record_audit_event

    record_audit_event(
        actor=username,
        actor_type="user",
        action="auth.login",
        entity_type="user",
        entity_id=username,
        metadata={},
    )


def _invalid_credentials_response(_username: str) -> Tuple[Dict[str, Any], int]:
    return {"error": "Invalid credentials"}, 401


def _role_from_grant(username: str, realm_roles) -> str:
    if username == ADMIN_USERNAME:
        return "admin"
    return role_from_realm_roles(realm_roles)


def _establish_session(session_obj: Any, username: str, role: str, logged_in: bool, reset_required: bool) -> None:
    session_obj.clear()
    session_obj.permanent = True
    session_obj["username"] = username
    session_obj["user_type"] = role
    session_obj["logged_in"] = logged_in
    if reset_required:
        session_obj["reset_required"] = True
    else:
        session_obj.pop("reset_required", None)
        initialize_session_tracking()


def login(data: Dict[str, Any], session_obj: Any) -> Tuple[Dict[str, Any], int]:
    if not data:
        return {"error": "No data provided"}, 400

    username = normalize_auth_key(data.get("username"))
    password = data.get("password")

    if not username or not password:
        return {"error": "Username and password required"}, 400

    cached = get_allowed_user_for_login(username)
    if cached:
        is_service = bool(cached[3]) if len(cached) > 3 else False
        auth_type = cached[2] if len(cached) > 2 else "ldap"
        if is_service or auth_type == "service":
            return _invalid_credentials_response(username)

    grant = password_grant(username, password)
    status = grant.get("status")

    if status == "reset_required" and not user_has_required_action(username, "UPDATE_PASSWORD"):
        try:
            prepare_user_for_raptor_login(username)
            grant = password_grant(username, password)
            status = grant.get("status")
        except Exception as exc:
            logger.warning("Could not complete Keycloak profile for %s: %s", username, exc)

    if status == "reset_required":
        if not user_has_required_action(username, "UPDATE_PASSWORD"):
            return _invalid_credentials_response(username)
        role = "admin" if username == ADMIN_USERNAME else (cached[1] if cached else "user")
        _establish_session(session_obj, username, role, logged_in=False, reset_required=True)
        return {
            "status": "password_reset_required",
            "username": username,
            "user_type": role,
            "permissions": list(get_user_permissions(username, role)),
        }, 200

    if status != "ok":
        return _invalid_credentials_response(username)

    realm_roles = grant.get("realm_roles") or []
    if ACCESS_ROLE not in realm_roles and username != ADMIN_USERNAME:
        return _invalid_credentials_response(username)
    if username == ADMIN_USERNAME and "raptor-admin" not in realm_roles and ACCESS_ROLE not in realm_roles:
        return _invalid_credentials_response(username)

    role = _role_from_grant(username, realm_roles)
    extra_permissions = grant.get("client_roles") or []
    claims = grant.get("claims") or {}
    keycloak_id = str(claims.get("sub") or "")
    detected = auth_type_for_username(username)
    auth_type = detected or ((cached[2] if cached and len(cached) > 2 else None) or ("local" if role == "admin" else "ldap"))
    if role != "admin":
        cache_from_login(username, role, extra_permissions, keycloak_id, auth_type)

    _establish_session(session_obj, username, role, logged_in=True, reset_required=False)
    _audit_login(username)
    return {
        "status": "logged_in",
        "username": username,
        "user_type": role,
        "permissions": list(get_user_permissions(username, role)),
    }, 200


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
        initialize_session_tracking()
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
        set_user_password(username, new_password, temporary=False)
        session_obj["logged_in"] = True
        session_obj["reset_required"] = False
        initialize_session_tracking()
        user_type = session_obj.get("user_type")
        return {
            "status": "logged_in",
            "username": username,
            "user_type": user_type,
            "permissions": list(get_user_permissions(username, user_type)),
        }, 200
    except LookupError:
        return {"error": "User not found."}, 404
    except Exception as exc:
        logger.error("Error resetting password for user %s: %s", username, exc)
        return {"error": "Failed to reset password."}, 500
