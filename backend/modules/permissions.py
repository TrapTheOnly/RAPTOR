"""Compatibility facade for permission and authorization utilities."""

from app.domain.auth.permissions import (
    PERMISSIONS,
    ROLE_DEFAULTS,
    ROLE_OPTIONAL,
    get_effective_permissions,
    sanitize_extra_permissions,
)
from app.http.decorators.permission_required import permission_required
from app.services.authorization_service import get_user_permissions, user_has_permission

__all__ = [
    "PERMISSIONS",
    "ROLE_DEFAULTS",
    "ROLE_OPTIONAL",
    "get_effective_permissions",
    "get_user_permissions",
    "permission_required",
    "sanitize_extra_permissions",
    "user_has_permission",
]
