import logging

from app.domain.auth.password_policy import validate_password_nist
from app.integrations.keycloak.client import password_grant
from app.repositories.admin_users_repository import (
    ADMIN_USERNAME,
    delete_user,
    get_existing_users,
)
from app.services.keycloak_bootstrap_service import bootstrap_keycloak
from app.services.keycloak_identity_service import set_user_password

logger = logging.getLogger(__name__)


def init_admin_db():
    bootstrap_keycloak()


def change_admin_password(current_password, new_password):
    grant = password_grant(ADMIN_USERNAME, current_password)
    if grant.get("status") != "ok":
        return {"error": "Current password is incorrect."}, 401

    ok, msg = validate_password_nist(new_password, username=ADMIN_USERNAME)
    if not ok:
        return {"error": msg}, 400
    if current_password == new_password:
        return {"error": "New password must be different from the current password."}, 400

    try:
        set_user_password(ADMIN_USERNAME, new_password, temporary=False)
        return {"message": "Password changed successfully."}, 200
    except LookupError:
        return {"error": "Admin user not found."}, 404
    except Exception as exc:
        logger.error("Error changing admin password: %s", exc)
        return {"error": "Failed to change password."}, 500


def reset_admin_password(new_password):
    ok, msg = validate_password_nist(new_password, username=ADMIN_USERNAME)
    if not ok:
        return {"error": msg}, 400

    try:
        set_user_password(ADMIN_USERNAME, new_password, temporary=False)
        return {"message": "Password reset successfully."}, 200
    except LookupError:
        return {"error": "Admin user not found."}, 404
    except Exception as exc:
        logger.error("Error resetting admin password: %s", exc)
        return {"error": "Failed to reset password."}, 500


__all__ = [
    "ADMIN_USERNAME",
    "change_admin_password",
    "delete_user",
    "get_existing_users",
    "init_admin_db",
    "reset_admin_password",
    "validate_password_nist",
]
