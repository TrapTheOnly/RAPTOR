"""Compatibility facade for user auth and LDAP helpers."""

from app.http.decorators.login_required import login_required_html, login_required_json
from app.integrations.ldap.client import (
    ldap_authenticate as _ldap_authenticate,
    search_ldap_users,
)
from app.services.admin_auth_service import ADMIN_USERNAME, admin_login


def ldap_authenticate(username, password):
    if username == ADMIN_USERNAME:
        return admin_login(username, password)
    return _ldap_authenticate(username, password)

__all__ = [
    "ldap_authenticate",
    "login_required_html",
    "login_required_json",
    "search_ldap_users",
]
