import logging
import os
import secrets
from typing import Any, Dict, List, Optional

from app.config import env_flag
from app.domain.auth.permissions import PERMISSIONS, ROLE_DEFAULTS, ROLE_OPTIONAL
from app.integrations.db.connection import get_db_connection
from app.integrations.keycloak.client import KeycloakAdminError, KeycloakClient
from app.integrations.keycloak.constants import (
    ACCESS_ROLE,
    BACKEND_CLIENT_ID,
    LDAP_COMPONENT_NAME,
    LOGIN_CLIENT_ID,
    REALM,
    ROLE_COMPOSITES,
    backend_client_secret,
    composite_for_role,
    keycloak_base_url,
    login_client_secret,
    login_redirect_uris,
    login_web_origins,
)
from app.repositories.admin_users_repository import (
    ADMIN_USERNAME,
    _write_initial_admin_credentials,
)
from app.repositories.users_repository import list_identity_cache_rows, upsert_identity_cache
from app.services import keycloak_identity_service as identity

logger = logging.getLogger(__name__)

_LOGIN_CLIENT_TEMPLATE = {
    "clientId": LOGIN_CLIENT_ID,
    "name": "RAPTOR login",
    "enabled": True,
    "protocol": "openid-connect",
    "publicClient": False,
    "bearerOnly": False,
    "standardFlowEnabled": True,
    "implicitFlowEnabled": False,
    "directAccessGrantsEnabled": True,
    "serviceAccountsEnabled": False,
    "frontchannelLogout": False,
    "fullScopeAllowed": True,
    "redirectUris": [],
    "webOrigins": [],
}

_BACKEND_CLIENT_TEMPLATE = {
    "clientId": BACKEND_CLIENT_ID,
    "name": "RAPTOR backend admin",
    "enabled": True,
    "protocol": "openid-connect",
    "publicClient": False,
    "bearerOnly": False,
    "standardFlowEnabled": False,
    "implicitFlowEnabled": False,
    "directAccessGrantsEnabled": False,
    "serviceAccountsEnabled": True,
    "frontchannelLogout": False,
    "fullScopeAllowed": True,
    "redirectUris": [],
    "webOrigins": [],
}


def _should_skip() -> bool:
    if env_flag("KEYCLOAK_BOOTSTRAP_SKIP", False):
        return True
    if os.getenv("RAPTOR_ROLE") == "worker":
        return True
    if not keycloak_base_url():
        return True
    return False


def _ensure_keycloak_schema() -> None:
    from app.config import DB_PATH

    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE SCHEMA IF NOT EXISTS keycloak")
        conn.commit()
    except Exception as exc:
        logger.warning("Could not ensure keycloak schema: %s", exc)
    finally:
        conn.close()


def _role_catalog() -> List[Dict[str, Any]]:
    return [
        {"name": ACCESS_ROLE, "description": "Allowlisted RAPTOR operator", "composite": False},
        *[
            {
                "name": ROLE_COMPOSITES[role],
                "description": f"RAPTOR {role} composite",
                "composite": True,
            }
            for role in ("user", "pentester", "manager", "admin")
        ],
    ]


def _ensure_role_catalog(client: KeycloakClient, login_uuid: str) -> None:
    for spec in _role_catalog():
        client.ensure_realm_role(spec["name"], spec["description"], composite=spec["composite"])
    permission_roles = {}
    for name in sorted(PERMISSIONS):
        permission_roles[name] = client.ensure_client_role(login_uuid, name)
    access_role = client.get_realm_role(ACCESS_ROLE)
    if not access_role:
        raise KeycloakAdminError("raptor-access role missing after ensure")
    for role_key, composite_name in ROLE_COMPOSITES.items():
        defaults = sorted(PERMISSIONS) if role_key == "admin" else sorted(ROLE_DEFAULTS.get(role_key, set()))
        client_role_reps = [permission_roles[name] for name in defaults if name in permission_roles]
        client.set_realm_role_composites(
            composite_name,
            realm_roles=[access_role],
            client_roles_by_uuid={login_uuid: client_role_reps},
        )
        unused = ROLE_OPTIONAL.get(role_key, set())
        for extra in unused:
            client.ensure_client_role(login_uuid, extra)


def _ensure_admin_user(client: KeycloakClient) -> None:
    existing = client.find_user(ADMIN_USERNAME)
    if existing:
        identity.assign_raptor_roles(client, str(existing["id"]), "admin", list(PERMISSIONS))
        logger.info("Keycloak admin user '%s' already exists.", ADMIN_USERNAME)
        return
    password = secrets.token_urlsafe(16)
    user_id = client.create_user(
        {
            "username": ADMIN_USERNAME,
            "enabled": True,
            "email": f"{ADMIN_USERNAME}@localhost",
            "emailVerified": True,
            "firstName": "Admin",
            "lastName": "User",
            "requiredActions": ["UPDATE_PASSWORD"],
        }
    )
    client.set_password(user_id, password, temporary=True)
    identity.assign_raptor_roles(client, user_id, "admin", list(PERMISSIONS))
    path = _write_initial_admin_credentials(ADMIN_USERNAME, password)
    if path:
        logger.warning(
            "Created Keycloak admin user '%s'. Initial password stored at '%s'.",
            ADMIN_USERNAME,
            path,
        )
    else:
        logger.warning("Created Keycloak admin user '%s' but could not persist the password file.", ADMIN_USERNAME)


def _env_flag_value(name: str, default: Optional[bool] = None) -> Optional[bool]:
    raw = str(os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _ldap_users_dn() -> str:
    override = str(os.getenv("LDAP_USERS_DN") or "").strip()
    if override:
        return override
    domain = str(os.getenv("LDAP_DOMAIN") or "").strip()
    if not domain:
        return ""
    return ",".join(f"DC={part}" for part in domain.split(".") if part)


def _ldap_vendor() -> str:
    vendor = str(os.getenv("LDAP_VENDOR") or "ad").strip().lower() or "ad"
    if vendor in {"ad", "active-directory", "active_directory"}:
        return "ad"
    if vendor in {"rhds", "redhat", "fedora"}:
        return "rhds"
    return vendor


def _ldap_attribute_defaults(vendor: str) -> Dict[str, str]:
    if vendor == "ad":
        return {
            "usernameLDAPAttribute": str(os.getenv("LDAP_USERNAME_ATTR") or "sAMAccountName").strip()
            or "sAMAccountName",
            "rdnLDAPAttribute": "cn",
            "uuidLDAPAttribute": str(os.getenv("LDAP_UUID_ATTR") or "objectGUID").strip() or "objectGUID",
            "userObjectClasses": str(os.getenv("LDAP_USER_OBJECT_CLASSES") or "person, organizationalPerson, user"),
        }
    return {
        "usernameLDAPAttribute": str(os.getenv("LDAP_USERNAME_ATTR") or "uid").strip() or "uid",
        "rdnLDAPAttribute": "uid",
        "uuidLDAPAttribute": str(os.getenv("LDAP_UUID_ATTR") or "entryUUID").strip() or "entryUUID",
        "userObjectClasses": str(os.getenv("LDAP_USER_OBJECT_CLASSES") or "inetOrgPerson, organizationalPerson"),
    }


def _ldap_truststore() -> str:
    value = str(os.getenv("LDAP_TRUSTSTORE") or "never").strip() or "never"
    if value not in {"never", "ldapsOnly", "always"}:
        return "never"
    return value


def _ldap_connection_candidates() -> List[Dict[str, str]]:
    server = str(os.getenv("LDAP_SERVER") or "").strip()
    if not server:
        return []
    start_tls_env = _env_flag_value("LDAP_START_TLS", False)
    start_tls = "true" if start_tls_env else "false"
    if server.startswith("ldap://") or server.startswith("ldaps://"):
        return [{"connectionUrl": server, "startTls": start_tls}]
    use_ssl = _env_flag_value("LDAP_USE_SSL")
    candidates: List[Dict[str, str]] = []
    if use_ssl is True:
        candidates.append({"connectionUrl": f"ldaps://{server}", "startTls": "false"})
    elif use_ssl is False:
        candidates.append({"connectionUrl": f"ldap://{server}", "startTls": start_tls})
    else:
        candidates.append({"connectionUrl": f"ldaps://{server}", "startTls": "false"})
        candidates.append({"connectionUrl": f"ldap://{server}", "startTls": "false"})
        if start_tls_env:
            candidates.append({"connectionUrl": f"ldap://{server}", "startTls": "true"})
        else:
            candidates.append({"connectionUrl": f"ldap://{server}", "startTls": "true"})
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for item in candidates:
        key = (item["connectionUrl"], item["startTls"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _probe_ldap_connection(client: KeycloakClient, bind_dn: str, bind_credential: str) -> Optional[Dict[str, str]]:
    truststore = _ldap_truststore()
    last_error = None
    for candidate in _ldap_connection_candidates():
        try:
            client.test_ldap_connection(
                "testConnection",
                candidate["connectionUrl"],
                bind_dn,
                bind_credential,
                use_truststore=truststore,
                start_tls=candidate["startTls"],
            )
            if bind_dn:
                client.test_ldap_connection(
                    "testAuthentication",
                    candidate["connectionUrl"],
                    bind_dn,
                    bind_credential,
                    use_truststore=truststore,
                    start_tls=candidate["startTls"],
                )
            logger.info(
                "Keycloak LDAP probe succeeded for %s (startTls=%s)",
                candidate["connectionUrl"],
                candidate["startTls"],
            )
            return candidate
        except KeycloakAdminError as exc:
            last_error = exc
            logger.warning(
                "Keycloak LDAP probe failed for %s (startTls=%s): %s",
                candidate["connectionUrl"],
                candidate["startTls"],
                exc,
            )
    if last_error:
        logger.error(
            "Could not reach LDAP from Keycloak. Set LDAP_SERVER to a reachable ldap(s):// URL, "
            "LDAP_USE_SSL=false for port 389, or LDAP_TRUSTSTORE=never for a private CA."
        )
    return None


def _disable_ldap_federation(client: KeycloakClient, reason: str) -> None:
    try:
        disabled = client.set_ldap_federation_enabled(False)
    except KeycloakAdminError as exc:
        logger.warning("Could not disable Keycloak LDAP federation: %s", exc)
        return
    if disabled:
        logger.warning("Disabled Keycloak LDAP federation (%s): %s", LDAP_COMPONENT_NAME, reason)
    else:
        logger.warning("Skipping Keycloak LDAP federation: %s", reason)


def _ensure_ldap(client: KeycloakClient) -> None:
    if not str(os.getenv("LDAP_SERVER") or "").strip():
        return
    users_dn = _ldap_users_dn()
    bind_dn = str(os.getenv("LDAP_USER") or "").strip()
    bind_credential = str(os.getenv("LDAP_PASS") or "").strip()
    if not users_dn:
        _disable_ldap_federation(client, "LDAP_DOMAIN/LDAP_USERS_DN is missing")
        return
    probed = _probe_ldap_connection(client, bind_dn, bind_credential)
    if not probed:
        _disable_ldap_federation(
            client,
            "directory is unreachable from Keycloak; RAPTOR login will keep using local Keycloak users",
        )
        return
    realm = client.get_realm() or {}
    realm_id = str(realm.get("id") or REALM)
    vendor = _ldap_vendor()
    attrs = _ldap_attribute_defaults(vendor)
    config = {
        "enabled": ["true"],
        "vendor": [vendor],
        "editMode": ["READ_ONLY"],
        "importEnabled": ["true"],
        "syncRegistrations": ["false"],
        "usernameLDAPAttribute": [attrs["usernameLDAPAttribute"]],
        "rdnLDAPAttribute": [attrs["rdnLDAPAttribute"]],
        "uuidLDAPAttribute": [attrs["uuidLDAPAttribute"]],
        "userObjectClasses": [attrs["userObjectClasses"]],
        "connectionUrl": [probed["connectionUrl"]],
        "usersDn": [users_dn],
        "authType": ["simple"],
        "bindDn": [bind_dn],
        "bindCredential": [bind_credential],
        "searchScope": ["2"],
        "pagination": ["true"],
        "startTls": [probed["startTls"]],
        "useTruststoreSpi": [_ldap_truststore()],
        "connectionPooling": ["true"],
        "trustEmail": ["true"],
        "validatePasswordPolicy": ["false"],
        "changedSyncPeriod": ["86400"],
        "fullSyncPeriod": ["-1"],
        "connectionTimeout": ["10000"],
        "readTimeout": ["10000"],
        "priority": ["0"],
    }
    component_id = client.ensure_ldap_federation(config, realm_id)
    logger.info(
        "Ensured Keycloak LDAP user federation '%s' against %s (id=%s)",
        LDAP_COMPONENT_NAME,
        probed["connectionUrl"],
        component_id or "unknown",
    )


def _idp_config_from_env() -> Optional[Dict[str, Any]]:
    alias = str(os.getenv("KEYCLOAK_IDP_ALIAS") or "").strip()
    provider = str(os.getenv("KEYCLOAK_IDP_PROVIDER") or "").strip().lower()
    if not alias or not provider:
        return None
    display = str(os.getenv("KEYCLOAK_IDP_DISPLAY_NAME") or alias).strip() or alias
    config: Dict[str, str] = {
        "syncMode": "IMPORT",
        "trustEmail": "true",
        "hideOnLoginPage": "true",
        "guiOrder": "0",
    }
    if provider in {"oidc", "keycloak-oidc"}:
        client_id = str(os.getenv("KEYCLOAK_IDP_CLIENT_ID") or "").strip()
        if not client_id:
            logger.warning("KEYCLOAK_IDP_ALIAS is set but KEYCLOAK_IDP_CLIENT_ID is missing; skipping identity provider")
            return None
        issuer = str(os.getenv("KEYCLOAK_IDP_ISSUER") or "").strip()
        authorization_url = str(os.getenv("KEYCLOAK_IDP_AUTHORIZATION_URL") or "").strip()
        token_url = str(os.getenv("KEYCLOAK_IDP_TOKEN_URL") or "").strip()
        if not issuer and not (authorization_url and token_url):
            logger.warning(
                "OIDC identity provider needs KEYCLOAK_IDP_ISSUER or KEYCLOAK_IDP_AUTHORIZATION_URL + KEYCLOAK_IDP_TOKEN_URL"
            )
            return None
        config.update(
            {
                "clientId": client_id,
                "clientSecret": str(os.getenv("KEYCLOAK_IDP_CLIENT_SECRET") or "").strip(),
                "defaultScope": "openid email profile",
                "clientAuthMethod": "client_secret_post",
                "validateSignature": "true",
                "useJwksUrl": "true",
            }
        )
        if issuer:
            config["issuer"] = issuer
        if authorization_url:
            config["authorizationUrl"] = authorization_url
        if token_url:
            config["tokenUrl"] = token_url
        jwks_url = str(os.getenv("KEYCLOAK_IDP_JWKS_URL") or "").strip()
        if jwks_url:
            config["jwksUrl"] = jwks_url
        logout_url = str(os.getenv("KEYCLOAK_IDP_LOGOUT_URL") or "").strip()
        if logout_url:
            config["logoutUrl"] = logout_url
    elif provider == "saml":
        entity_id = str(os.getenv("KEYCLOAK_IDP_ENTITY_ID") or os.getenv("KEYCLOAK_IDP_ISSUER") or "").strip()
        sso_url = str(os.getenv("KEYCLOAK_IDP_SSO_URL") or os.getenv("KEYCLOAK_IDP_AUTHORIZATION_URL") or "").strip()
        if not entity_id or not sso_url:
            logger.warning("SAML identity provider needs KEYCLOAK_IDP_ENTITY_ID and KEYCLOAK_IDP_SSO_URL")
            return None
        config.update(
            {
                "entityId": entity_id,
                "singleSignOnServiceUrl": sso_url,
                "nameIDPolicyFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
                "principalType": "SUBJECT",
                "wantAuthnRequestsSigned": "false",
                "postBindingAuthnRequest": "true",
                "postBindingResponse": "true",
            }
        )
        logout_url = str(os.getenv("KEYCLOAK_IDP_LOGOUT_URL") or "").strip()
        if logout_url:
            config["singleLogoutServiceUrl"] = logout_url
    else:
        logger.warning("Unsupported KEYCLOAK_IDP_PROVIDER=%s (use oidc, keycloak-oidc, or saml)", provider)
        return None
    return {
        "alias": alias,
        "displayName": display,
        "providerId": provider,
        "enabled": True,
        "updateProfileFirstLoginMode": "off",
        "trustEmail": True,
        "storeToken": False,
        "linkOnly": False,
        "firstBrokerLoginFlowAlias": "first broker login",
        "config": config,
    }


def _login_client_representation() -> Dict[str, Any]:
    return {
        **_LOGIN_CLIENT_TEMPLATE,
        "secret": login_client_secret(),
        "redirectUris": login_redirect_uris(),
        "webOrigins": login_web_origins(),
    }


def _ensure_identity_provider(client: KeycloakClient) -> None:
    representation = _idp_config_from_env()
    if not representation:
        return
    alias = str(representation.get("alias") or "").strip()
    if client.get_identity_provider(alias):
        logger.info("Skipping env identity-provider seed; '%s' already exists", alias)
        return
    created = client.ensure_identity_provider(representation)
    logger.info(
        "Ensured Keycloak identity provider '%s' (%s)",
        created.get("alias") or representation["alias"],
        created.get("providerId") or representation["providerId"],
    )


def _meta_flag(key: str) -> Optional[str]:
    from app.config import DB_PATH

    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_meta WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            return None
        return row[0] if not isinstance(row, dict) else row.get("value")
    finally:
        conn.close()


def _set_meta_flag(key: str, value: str) -> None:
    from app.config import DB_PATH

    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO app_meta (key, value) VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def _write_migration_secrets(filename: str, header: str, lines: List[str]) -> None:
    from app.config import DATA_PATH

    target = os.path.join(DATA_PATH, filename)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(header + "\n")
            handle.write("warning=One-time credentials; previous secrets cannot be recovered.\n")
            handle.write("\n".join(lines))
            handle.write("\n")
        logger.warning("Wrote migrated credentials to %s", target)
    except Exception as exc:
        logger.error("Could not persist %s: %s", filename, exc)


def _migrate_existing_identities(client: KeycloakClient) -> None:
    if _meta_flag("keycloak_identity_migrated") == "1":
        return
    rows = list_identity_cache_rows()
    migrated_secrets: List[str] = []
    migrated_locals: List[str] = []
    for row in rows:
        username = str(row.get("username") or "").strip().lower()
        if not username or username == ADMIN_USERNAME:
            continue
        try:
            if row.get("is_service_account"):
                secret = identity.migrate_service_account(client, row)
                if secret:
                    migrated_secrets.append(f"{username}={secret}")
                continue
            auth_type = str(row.get("auth_type") or "ldap").lower()
            temp = identity.migrate_interactive_user(client, row, force_password_reset=(auth_type == "local"))
            if temp:
                migrated_locals.append(f"{username}={temp}")
        except Exception as exc:
            logger.error("Failed to migrate identity %s into Keycloak: %s", username, exc)
    if migrated_secrets:
        _write_migration_secrets("migrated_service_account_keys.txt", "RAPTOR migrated service-account API keys", migrated_secrets)
    if migrated_locals:
        _write_migration_secrets(
            "migrated_local_user_passwords.txt",
            "RAPTOR migrated local-user temporary passwords",
            migrated_locals,
        )
    _set_meta_flag("keycloak_identity_migrated", "1")


def bootstrap_keycloak() -> None:
    if _should_skip():
        logger.info("Skipping Keycloak bootstrap")
        return
    if not login_client_secret() or not backend_client_secret():
        logger.warning("Keycloak client secrets are not set; skipping bootstrap")
        return
    _ensure_keycloak_schema()
    client = KeycloakClient()
    client.wait_ready()
    realm = client.get_realm()
    if not realm:
        logger.info("Creating Keycloak realm '%s'", REALM)
        client.create_realm(
            {
                "realm": REALM,
                "enabled": True,
                "displayName": "RAPTOR",
                "registrationAllowed": False,
                "sslRequired": "none",
                "bruteForceProtected": True,
                "failureFactor": 5,
                "waitIncrementSeconds": 60,
                "maxFailureWaitSeconds": 900,
                "passwordPolicy": "length(12) and maxLength(64) and notUsername",
                "accessTokenLifespan": 3600,
                "ssoSessionIdleTimeout": 3600,
                "ssoSessionMaxLifespan": 28800,
            }
        )
    login_rep = _login_client_representation()
    backend_rep = {**_BACKEND_CLIENT_TEMPLATE, "secret": backend_client_secret()}
    login_client = client.ensure_client(login_rep)
    client.ensure_client(backend_rep)
    _ensure_ldap(client)
    try:
        client.ensure_backend_service_account_privileges()
    except KeycloakAdminError as exc:
        logger.warning("Could not grant raptor-backend realm-management roles: %s", exc)
    _ensure_role_catalog(client, str(login_client["id"]))
    try:
        client.ensure_direct_grant_allowlist_flow()
    except KeycloakAdminError as exc:
        logger.warning("Direct-grant allowlist flow setup failed; Flask still enforces raptor-access: %s", exc)
    try:
        _ensure_admin_user(client)
    except KeycloakAdminError as exc:
        logger.error("Could not ensure Keycloak admin user: %s", exc)
    try:
        client.relax_user_profile_required_attributes()
    except KeycloakAdminError as exc:
        logger.warning("Could not relax Keycloak user profile: %s", exc)
    try:
        _ensure_identity_provider(client)
    except KeycloakAdminError as exc:
        logger.warning("Could not ensure Keycloak identity provider: %s", exc)
    _migrate_existing_identities(client)
    logger.info("Keycloak identity bootstrap complete")


def init_admin_db() -> None:
    bootstrap_keycloak()


__all__ = ["bootstrap_keycloak", "init_admin_db"]
