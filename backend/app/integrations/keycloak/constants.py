import os

from app.domain.auth.permissions import PERMISSIONS, ROLE_DEFAULTS, ROLE_OPTIONAL

REALM = os.getenv("KEYCLOAK_REALM", "raptor").strip() or "raptor"
LOGIN_CLIENT_ID = os.getenv("KEYCLOAK_LOGIN_CLIENT_ID", "raptor-login").strip() or "raptor-login"
BACKEND_CLIENT_ID = os.getenv("KEYCLOAK_BACKEND_CLIENT_ID", "raptor-backend").strip() or "raptor-backend"

ACCESS_ROLE = "raptor-access"
ROLE_COMPOSITES = {
    "user": "raptor-user",
    "pentester": "raptor-pentester",
    "manager": "raptor-manager",
    "admin": "raptor-admin",
}
COMPOSITE_TO_ROLE = {value: key for key, value in ROLE_COMPOSITES.items()}
RAPTOR_REALM_ROLES = frozenset({ACCESS_ROLE, *ROLE_COMPOSITES.values()})
SERVICE_CLIENT_PREFIX = "svc-"
SERVICE_SCOPE_ROLES = ("records.read", "pentests.read", "pentests.write")
BACKEND_MANAGEMENT_ROLES = (
    "manage-users",
    "view-users",
    "query-users",
    "manage-clients",
    "view-clients",
    "query-clients",
    "manage-realm",
    "view-realm",
    "query-realms",
    "manage-identity-providers",
    "view-identity-providers",
)
DIRECT_GRANT_FLOW = "raptor direct grant"
LDAP_COMPONENT_NAME = "raptor-ldap"
MASTER_REALM = "master"


def keycloak_base_url() -> str:
    return str(os.getenv("KEYCLOAK_URL") or "http://keycloak:8080").rstrip("/")


def login_client_secret() -> str:
    return str(os.getenv("KEYCLOAK_LOGIN_CLIENT_SECRET") or "").strip()


def backend_client_secret() -> str:
    return str(os.getenv("KEYCLOAK_BACKEND_CLIENT_SECRET") or "").strip()


def master_admin_username() -> str:
    return str(os.getenv("KEYCLOAK_ADMIN") or "admin").strip() or "admin"


def master_admin_password() -> str:
    return str(os.getenv("KEYCLOAK_ADMIN_PASSWORD") or "").strip()


def service_client_id(username: str) -> str:
    return f"{SERVICE_CLIENT_PREFIX}{username}"


def composite_for_role(role: str) -> str:
    return ROLE_COMPOSITES.get(str(role or "user").strip().lower(), ROLE_COMPOSITES["user"])


def role_from_realm_roles(realm_roles) -> str:
    names = {str(item or "") for item in (realm_roles or [])}
    for key in ("admin", "manager", "pentester", "user"):
        if ROLE_COMPOSITES[key] in names:
            return key
    return "user"


def default_permission_names(role: str):
    if role == "admin":
        return sorted(PERMISSIONS)
    return sorted(ROLE_DEFAULTS.get(role, set()))


def optional_permission_names(role: str):
    return sorted(ROLE_OPTIONAL.get(role, set()))


__all__ = [
    "ACCESS_ROLE",
    "BACKEND_CLIENT_ID",
    "BACKEND_MANAGEMENT_ROLES",
    "COMPOSITE_TO_ROLE",
    "DIRECT_GRANT_FLOW",
    "LDAP_COMPONENT_NAME",
    "LOGIN_CLIENT_ID",
    "MASTER_REALM",
    "RAPTOR_REALM_ROLES",
    "REALM",
    "ROLE_COMPOSITES",
    "SERVICE_CLIENT_PREFIX",
    "SERVICE_SCOPE_ROLES",
    "backend_client_secret",
    "composite_for_role",
    "default_permission_names",
    "keycloak_base_url",
    "login_client_secret",
    "master_admin_password",
    "master_admin_username",
    "optional_permission_names",
    "role_from_realm_roles",
    "service_client_id",
]
