"""
Compatibility shim: re-export auth helpers from app.services.auth.
"""
from app.services.auth import (  # noqa: F401
    ldap_authenticate,
    search_ldap_users,
    login_required_json,
    login_required_html,
)
