import os
from typing import List
from urllib.parse import urlparse

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
SSO_CALLBACK_PATH = "/auth/sso/callback"
SSO_PROVIDER_IDS = frozenset({"oidc", "keycloak-oidc", "saml"})


def keycloak_base_url() -> str:
    return str(os.getenv("KEYCLOAK_URL") or "http://keycloak:8080").rstrip("/")


def keycloak_public_url() -> str:
    explicit = str(os.getenv("KEYCLOAK_PUBLIC_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    internal = keycloak_base_url()
    host = (urlparse(internal).hostname or "").lower()
    if host in {"keycloak", "raptor-keycloak-dev", "raptor-keycloak-prod"}:
        return "http://localhost:8180"
    return internal


def raptor_public_url() -> str:
    explicit = str(os.getenv("RAPTOR_PUBLIC_URL") or os.getenv("PUBLIC_APP_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    for origin in str(os.getenv("CORS_ORIGINS") or "").split(","):
        candidate = origin.strip().rstrip("/")
        if candidate and candidate != "*":
            return candidate
    return "http://localhost:1337"


def sso_callback_url() -> str:
    return f"{raptor_public_url()}{SSO_CALLBACK_PATH}"


def login_redirect_uris() -> List[str]:
    uris = {sso_callback_url(), f"http://localhost:1337{SSO_CALLBACK_PATH}"}
    return sorted(uris)


def login_web_origins() -> List[str]:
    origins = {raptor_public_url(), "http://localhost:1337"}
    return sorted(origins)


def sso_protocol(provider_id: str) -> str:
    value = str(provider_id or "").strip().lower()
    if value == "saml":
        return "saml"
    return "oidc"


def is_supported_sso_provider(provider_id: str) -> bool:
    return str(provider_id or "").strip().lower() in SSO_PROVIDER_IDS


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
    "SSO_CALLBACK_PATH",
    "SSO_PROVIDER_IDS",
    "backend_client_secret",
    "composite_for_role",
    "default_permission_names",
    "is_supported_sso_provider",
    "keycloak_base_url",
    "keycloak_public_url",
    "login_client_secret",
    "login_redirect_uris",
    "login_web_origins",
    "master_admin_password",
    "master_admin_username",
    "optional_permission_names",
    "raptor_public_url",
    "role_from_realm_roles",
    "service_client_id",
    "sso_callback_url",
    "sso_protocol",
]
