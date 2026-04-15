import json
import logging
import secrets
from typing import Any, Callable, Dict, Tuple

import bcrypt

from app.integrations.db.connection import IntegrityError
from app.http.request_utils import normalize_auth_key
from app.repositories.users_repository import (
    add_allowed_user,
    get_user_role,
    is_service_account_user,
    remove_user_from_pentest_collaborations,
    update_user_permissions as update_user_permissions_repo,
    update_user_role as update_user_role_repo,
)
from app.services.admin_auth_service import (
    ADMIN_USERNAME,
    change_admin_password,
    delete_user,
    get_existing_users,
)
from app.domain.auth.permissions import sanitize_extra_permissions
from app.integrations.ldap.client import search_ldap_users

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
    try:
        sanitized_permissions = sanitize_extra_permissions(role, permissions)
        add_allowed_user(
            username=username,
            email=email,
            role=role,
            auth_type=auth_type,
            password_hash=password_hash,
            must_reset=must_reset,
            permissions_json=json.dumps(sanitized_permissions),
            is_service_account=1 if is_service_account else 0,
            full_name=full_name,
        )
        logger.info(f"User {username} added to the system with role {role}.")
    except IntegrityError:
        raise ValueError(f"User {username} already exists in the system.")
    except Exception as e:
        raise RuntimeError(f"Error adding user {username}: {e}")


def ldap_search(query: str) -> Tuple[Dict[str, Any], int]:
    if not query:
        return {"error": "Query parameter is required."}, 400

    try:
        results = search_ldap_users(query.lower())
        return {"results": results}, 200
    except Exception as e:
        logger.error(f"LDAP search failed: {e}")
        return {"error": "LDAP search failed."}, 500


def add_user(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = str(data.get("username") or "").strip().lower()
    email = str(data.get("email") or "").strip().lower()
    role = str(data.get("role", "user")).strip().lower()
    permissions = data.get("permissions", [])
    full_name = str(data.get("full_name") or "").strip() or None

    if not username:
        return {"error": "Username is required."}, 400
    if not email:
        return {"error": "Email is required."}, 400
    if not isinstance(permissions, list):
        return {"error": "Permissions must be a list."}, 400
    if role not in ["user", "pentester", "manager"]:
        return {"error": "Invalid role specified."}, 400

    try:
        add_user_to_system(username, email, role, auth_type="ldap", permissions=permissions, full_name=full_name)
        return {"message": f"User {username} added successfully with role {role}."}, 200
    except Exception as e:
        logger.error(f"Error adding user {username}: {e}")
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
            add_user_to_system(
                username=username,
                email="",
                role="user",
                auth_type="service",
                password_hash=None,
                must_reset=0,
                permissions=[],
                is_service_account=True,
                full_name=full_name,
            )
            return {
                "message": f"Service account {username} created successfully.",
                "is_service_account": True,
            }, 200

        temp_password = secrets.token_urlsafe(12)
        if len(temp_password) < 12:
            temp_password = temp_password + secrets.token_urlsafe(12)
        temp_password = temp_password[:32]

        hashed_password = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt())
        add_user_to_system(
            username=username,
            email="",
            role=role,
            auth_type="local",
            password_hash=hashed_password,
            must_reset=1,
            permissions=permissions,
            is_service_account=False,
            full_name=full_name,
        )
        return {
            "message": f"Local user {username} created successfully.",
            "temp_password": temp_password,
            "is_service_account": False,
        }, 200
    except Exception as e:
        logger.error(f"Error adding local user {username}: {e}")
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
        rowcount = update_user_role_repo(username, new_role, json.dumps([]))
        if rowcount == 0:
            return {"error": f"User {username} not found"}, 404
        return {"message": f"Role for user {username} updated to {new_role}"}, 200
    except Exception as e:
        logger.error(f"Error updating role for user {username}: {e}")
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
        role = get_user_role(username)
        if role is None:
            return {"error": f"User {username} not found"}, 404

        sanitized = sanitize_extra_permissions(role, requested_permissions)
        if set(requested_permissions) - set(sanitized):
            return {"error": "Invalid permissions for role"}, 400

        update_user_permissions_repo(username, json.dumps(sanitized))
        return {
            "message": "User permissions updated.",
            "permissions": sanitized,
        }, 200
    except Exception as e:
        logger.error(f"Error updating permissions for user {username}: {e}")
        return {"error": "Failed to update user permissions"}, 500


def delete_user_service(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = normalize_auth_key(data.get("username"))

    if not username:
        return {"error": "Username is required."}, 400

    try:
        remove_user_from_pentest_collaborations(username)
    except Exception as e:
        logger.warning(f"Failed to remove '{username}' from pentest collaborations before delete: {e}")

    response, status_code = delete_user(username)
    return response, status_code


def manual_update(update_fn: Callable[[], None]) -> Tuple[Dict[str, Any], int]:
    try:
        update_fn()
        return {"status": "success", "message": "Records updated successfully."}, 200
    except Exception as e:
        logger.error(f"Manual update error: {e}")
        return {"status": "error", "message": "Failed to update records."}, 500
