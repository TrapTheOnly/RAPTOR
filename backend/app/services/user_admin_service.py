import logging
import os
from typing import Any, Dict, Tuple

from app.http.request_utils import normalize_auth_key
from app.integrations.db.connection import IntegrityError
from app.repositories.users_repository import is_service_account_user
from app.services.admin_auth_service import (
    ADMIN_USERNAME,
    change_admin_password,
    get_existing_users,
)
from app.services.keycloak_identity_service import (
    delete_user,
    provision_ldap_user,
    provision_local_user,
    provision_service_account,
    search_directory_users,
    update_optional_permissions,
    update_role,
)

logger = logging.getLogger(__name__)


def add_user_to_system(
    username: str,
    email: str,
    role: str = "user",
    auth_type: str = "ldap",
    password_hash: Any = None,
    must_reset: int = 0,
    permissions: Any = None,
    is_service_account: bool = False,
    full_name: str = None,
) -> None:
    del password_hash, must_reset
    if is_service_account:
        provision_service_account(username, full_name=full_name)
        return
    if auth_type == "local":
        provision_local_user(username, role, permissions or [], full_name=full_name)
        return
    provision_ldap_user(username, email, role, permissions or [], full_name=full_name)


def ldap_search(query: str) -> Tuple[Dict[str, Any], int]:
    if not query:
        return {"error": "Query parameter is required."}, 400

    try:
        results = search_directory_users(query.lower())
        return {"results": results}, 200
    except Exception as exc:
        logger.error("Directory search failed: %s", exc)
        return {"error": "LDAP search failed."}, 500


def add_user(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = str(data.get("username") or "").strip().lower()
    email = str(data.get("email") or "").strip().lower()
    role = str(data.get("role", "user")).strip().lower()
    permissions = data.get("permissions", [])
    full_name = str(data.get("full_name") or "").strip() or None

    if not username:
        return {"error": "Username is required."}, 400
    if not isinstance(permissions, list):
        return {"error": "Permissions must be a list."}, 400
    if role not in ["user", "pentester", "manager"]:
        return {"error": "Invalid role specified."}, 400
    if not email:
        domain = str(os.getenv("LDAP_DOMAIN") or "directory.local").strip() or "directory.local"
        email = f"{username}@{domain}"

    try:
        provision_ldap_user(username, email, role, permissions, full_name=full_name)
        return {"message": f"User {username} added successfully with role {role}."}, 200
    except LookupError as exc:
        return {"error": str(exc)}, 404
    except IntegrityError:
        return {"error": f"User {username} already exists in the system."}, 500
    except Exception as exc:
        logger.error("Error adding user %s: %s", username, exc)
        return {"error": "Failed to add user."}, 500


def add_local_user(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = str(data.get("username") or "").strip().lower()
    role = str(data.get("role", "user")).strip().lower()
    permissions = data.get("permissions", [])
    is_service_account = bool(data.get("is_service_account"))
    full_name = str(data.get("full_name") or "").strip() or None

    if not username:
        return {"error": "Username is required."}, 400
    if username == ADMIN_USERNAME:
        return {"error": "Username is reserved."}, 400
    if role not in ["user", "pentester", "manager"]:
        return {"error": "Invalid role specified."}, 400
    if not isinstance(permissions, list):
        return {"error": "Permissions must be a list."}, 400

    try:
        if is_service_account:
            provision_service_account(username, full_name=full_name)
            return {
                "message": f"Service account {username} created successfully.",
                "is_service_account": True,
            }, 200

        _user_id, temp_password = provision_local_user(username, role, permissions, full_name=full_name)
        return {
            "message": f"Local user {username} created successfully.",
            "temp_password": temp_password,
            "is_service_account": False,
        }, 200
    except ValueError as exc:
        logger.error("Error adding local user %s: %s", username, exc)
        return {"error": str(exc)}, 500
    except Exception as exc:
        logger.error("Error adding local user %s: %s", username, exc)
        return {"error": "Failed to create local user."}, 500


def change_password(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return {"error": "Both current and new passwords are required."}, 400

    response, status_code = change_admin_password(current_password, new_password)
    return response, status_code


def get_existing_users_service() -> Tuple[Dict[str, Any], int]:
    response, status_code = get_existing_users()
    return response, status_code


def update_user_role(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = normalize_auth_key(data.get("username"))
    new_role = str(data.get("role") or "").strip().lower()

    if not username or not new_role:
        return {"error": "Username and role are required"}, 400
    if new_role not in ["user", "pentester", "manager"]:
        return {"error": "Invalid user role"}, 400

    try:
        if is_service_account_user(username):
            return {"error": "Service account role cannot be changed."}, 400
        rowcount = update_role(username, new_role)
        if rowcount == 0:
            return {"error": f"User {username} not found"}, 404
        return {"message": f"Role for user {username} updated to {new_role}"}, 200
    except Exception as exc:
        logger.error("Error updating role for user %s: %s", username, exc)
        return {"error": "Failed to update user role"}, 500


def update_user_permissions(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = normalize_auth_key(data.get("username"))
    requested_permissions = data.get("permissions", [])

    if not username:
        return {"error": "Username is required"}, 400
    if not isinstance(requested_permissions, list):
        return {"error": "Permissions must be a list"}, 400

    try:
        if is_service_account_user(username):
            return {"error": "Service account permissions are managed via API privileges."}, 400
        sanitized = update_optional_permissions(username, requested_permissions)
        if set(requested_permissions) - set(sanitized):
            return {"error": "Invalid permissions for role"}, 400
        return {
            "message": "User permissions updated.",
            "permissions": sanitized,
        }, 200
    except LookupError:
        return {"error": f"User {username} not found"}, 404
    except Exception as exc:
        logger.error("Error updating permissions for user %s: %s", username, exc)
        return {"error": "Failed to update user permissions"}, 500


def delete_user_service(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = normalize_auth_key(data.get("username"))

    if not username:
        return {"error": "Username is required."}, 400

    try:
        return delete_user(username)
    except Exception as exc:
        logger.error("Error deleting user %s: %s", username, exc)
        return {"error": "Failed to delete user."}, 500
