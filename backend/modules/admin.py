"""Compatibility facade for admin auth and user-management helpers."""

from app.domain.auth.password_policy import (
    COMMON_PASSWORDS,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    validate_password_nist,
)
from app.http.decorators.admin_required import admin_or_manager_required, admin_required
from app.repositories.admin_users_repository import ADMIN_USERNAME
from app.services.admin_auth_service import (
    admin_login,
    admin_requires_password_reset,
    change_admin_password,
    delete_user,
    get_existing_users,
    init_admin_db,
    reset_admin_password,
)

__all__ = [
    "ADMIN_USERNAME",
    "COMMON_PASSWORDS",
    "MAX_PASSWORD_LENGTH",
    "MIN_PASSWORD_LENGTH",
    "admin_login",
    "admin_or_manager_required",
    "admin_required",
    "admin_requires_password_reset",
    "change_admin_password",
    "delete_user",
    "get_existing_users",
    "init_admin_db",
    "reset_admin_password",
    "validate_password_nist",
]
