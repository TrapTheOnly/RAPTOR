import logging

from app.domain.auth.password_policy import validate_password_nist
from app.repositories.admin_users_repository import (
    ADMIN_USERNAME,
    admin_login,
    admin_requires_password_reset,
    check_current_admin_password,
    delete_user,
    ensure_admin_user_exists,
    get_existing_users,
    update_admin_password,
)

logger = logging.getLogger(__name__)


def init_admin_db():
    ensure_admin_user_exists()


def change_admin_password(current_password, new_password):
    if not check_current_admin_password(current_password):
        return {"error": "Current password is incorrect."}, 401

    ok, msg = validate_password_nist(new_password, username=ADMIN_USERNAME)
    if not ok:
        return {"error": msg}, 400

    try:
        result = update_admin_password(new_password)
        if result == "not_found":
            return {"error": "Admin user not found."}, 404
        if result == "same_password":
            return {"error": "New password must be different from the current password."}, 400
        return {"message": "Password changed successfully."}, 200
    except Exception as exc:
        logger.error(f"Error changing admin password: {exc}")
        return {"error": "Failed to change password."}, 500


def reset_admin_password(new_password):
    ok, msg = validate_password_nist(new_password, username=ADMIN_USERNAME)
    if not ok:
        return {"error": msg}, 400

    try:
        result = update_admin_password(new_password)
        if result == "not_found":
            return {"error": "Admin user not found."}, 404
        if result == "same_password":
            return {"error": "New password must be different from the temporary password."}, 400
        return {"message": "Password reset successfully."}, 200
    except Exception as exc:
        logger.error(f"Error resetting admin password: {exc}")
        return {"error": "Failed to reset password."}, 500


__all__ = [
    "ADMIN_USERNAME",
    "admin_login",
    "admin_requires_password_reset",
    "change_admin_password",
    "delete_user",
    "get_existing_users",
    "init_admin_db",
    "reset_admin_password",
    "validate_password_nist",
]
