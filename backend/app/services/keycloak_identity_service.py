import json
import logging
import os
import secrets
from typing import Any, Dict, List, Optional, Tuple

from app.domain.auth.permissions import sanitize_extra_permissions
from app.integrations.keycloak.client import (
    KeycloakAdminError,
    KeycloakClient,
    admin_client,
    client_credentials_grant,
)
from app.integrations.keycloak.constants import (
    ACCESS_ROLE,
    LOGIN_CLIENT_ID,
    composite_for_role,
    service_client_id,
)
from app.repositories.users_repository import (
    add_allowed_user,
    delete_identity,
    get_user_role,
    is_service_account_user,
    list_identity_cache_rows,
    remove_user_from_pentest_collaborations,
    update_user_keycloak_id,
    update_user_permissions as update_user_permissions_repo,
    update_user_role as update_user_role_repo,
    upsert_identity_cache,
)
from app.repositories.service_api_repository import (
    create_service_account,
    get_service_account_by_username,
    get_service_account_with_key,
    rotate_service_account_key,
    update_service_account_keycloak_client,
    update_service_account_scopes,
)

logger = logging.getLogger(__name__)


def _client() -> KeycloakClient:
    return admin_client()


def _login_client_uuid(client: KeycloakClient) -> str:
    row = client.get_client_by_client_id(LOGIN_CLIENT_ID)
    if not row:
        raise KeycloakAdminError("raptor-login client is missing")
    return str(row["id"])


def _role_reps(client: KeycloakClient, names: List[str]) -> List[Dict[str, Any]]:
    reps = []
    for name in names:
        row = client.get_realm_role(name)
        if row:
            reps.append(row)
    return reps


def assign_raptor_roles(
    client: KeycloakClient,
    user_id: str,
    role: str,
    extra_permissions: Optional[List[str]] = None,
) -> List[str]:
    sanitized = sanitize_extra_permissions(role, extra_permissions or [])
    composite = composite_for_role(role)
    realm_roles = _role_reps(client, [ACCESS_ROLE, composite])
    client.replace_user_raptor_realm_roles(user_id, realm_roles)
    login_uuid = _login_client_uuid(client)
    permission_roles = []
    for name in sanitized:
        permission_roles.append(client.ensure_client_role(login_uuid, name))
    client.replace_user_client_roles(user_id, login_uuid, permission_roles)
    return sanitized


def _display_name(user: Dict[str, Any]) -> Optional[str]:
    first = str(user.get("firstName") or "").strip()
    last = str(user.get("lastName") or "").strip()
    combined = " ".join(part for part in (first, last) if part)
    return combined or None


def _split_full_name(full_name: Optional[str]) -> Tuple[str, str]:
    text = str(full_name or "").strip()
    if not text:
        return "", ""
    parts = text.split(" ", 1)
    first = parts[0].strip()
    last = parts[1].strip() if len(parts) > 1 else ""
    return first, last


def _sso_placeholder_profile(username: str, full_name: Optional[str] = None) -> Dict[str, str]:
    """Satisfy required Keycloak user attributes without using the IdP email.

    Auto-link must match username only. A real invite email on the Keycloak
    user would let a different IdP account claim the placeholder by email.
    """
    first_name, last_name = _split_full_name(full_name)
    handle = str(username or "").strip() or "sso"
    if not first_name:
        first_name = handle.split("@", 1)[0] or handle
    if not last_name:
        last_name = "SSO"
    email_local = handle.replace("@", ".")
    return {
        "firstName": first_name,
        "lastName": last_name,
        "email": f"{email_local}@sso.invalid",
        "emailVerified": False,
    }


def _source_label(auth_type: str) -> str:
    return {
        "ldap": "LDAP",
        "oidc": "OIDC",
        "saml": "SAML",
        "federated": "Directory",
        "local": "Local",
        "service": "Service",
    }.get(auth_type, "Directory")


def auth_type_from_keycloak_user(
    user: Dict[str, Any],
    federated_identities: Optional[List[Dict[str, Any]]] = None,
    identity_providers: Optional[List[Dict[str, Any]]] = None,
) -> str:
    username = str(user.get("username") or "")
    if username.startswith("service-account-"):
        return "service"
    if str(user.get("federationLink") or "").strip():
        return "ldap"
    identities = federated_identities or []
    if not identities:
        return "local"
    alias = str((identities[0] or {}).get("identityProvider") or "").strip().lower()
    provider_by_alias = {
        str(row.get("alias") or "").strip().lower(): str(row.get("providerId") or "").strip().lower()
        for row in (identity_providers or [])
        if isinstance(row, dict)
    }
    provider = provider_by_alias.get(alias, "")
    if provider in {"saml"} or "saml" in alias:
        return "saml"
    if provider in {"oidc", "keycloak-oidc"} or "oidc" in alias:
        return "oidc"
    return "federated"


def _directory_row_from_keycloak(
    row: Dict[str, Any],
    *,
    federated_identities: Optional[List[Dict[str, Any]]] = None,
    identity_providers: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    username = str(row.get("username") or "").strip()
    if not username or username.startswith("service-account-"):
        return None
    auth_type = auth_type_from_keycloak_user(row, federated_identities, identity_providers)
    email = str(row.get("email") or "").strip()
    return {
        "username": username,
        "email": email,
        "full_name": _display_name(row) or username,
        "distinguished_name": None,
        "keycloak_id": row.get("id"),
        "auth_type": auth_type,
        "source": _source_label(auth_type),
    }


def _merge_directory_row(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key in ("email", "full_name", "distinguished_name", "keycloak_id", "auth_type", "source"):
        if not merged.get(key) and incoming.get(key):
            merged[key] = incoming[key]
    if incoming.get("keycloak_id") and not existing.get("keycloak_id"):
        merged["keycloak_id"] = incoming["keycloak_id"]
        merged["auth_type"] = incoming.get("auth_type") or merged.get("auth_type")
        merged["source"] = incoming.get("source") or merged.get("source")
    return merged


def search_directory_users(query: str) -> List[Dict[str, Any]]:
    needle = str(query or "").strip()
    if not needle:
        return []
    by_username: Dict[str, Dict[str, Any]] = {}
    keycloak_ok = False
    try:
        client = _client()
        rows = list(client.search_users(needle, max_results=50))
        exact = client.find_user(needle)
        if exact:
            exact_id = exact.get("id")
            rows = [exact] + [row for row in rows if row.get("id") != exact_id]
        for row in rows:
            mapped = _directory_row_from_keycloak(row)
            if not mapped:
                continue
            key = mapped["username"].lower()
            if key in by_username:
                by_username[key] = _merge_directory_row(by_username[key], mapped)
            else:
                by_username[key] = mapped
        keycloak_ok = True
    except Exception as exc:
        logger.warning("Keycloak directory search failed: %s", exc)
    if os.getenv("LDAP_SERVER") and (not by_username or not keycloak_ok):
        try:
            from app.integrations.ldap.client import search_ldap_users

            for item in search_ldap_users(needle):
                username = str(item.get("username") or "").strip()
                if not username:
                    continue
                mapped = {
                    "username": username,
                    "email": str(item.get("email") or "").strip(),
                    "full_name": item.get("full_name") or username,
                    "distinguished_name": item.get("distinguished_name"),
                    "keycloak_id": None,
                    "auth_type": "ldap",
                    "source": "LDAP",
                }
                key = username.lower()
                if key in by_username:
                    by_username[key] = _merge_directory_row(by_username[key], mapped)
                else:
                    by_username[key] = mapped
        except Exception as exc:
            if not by_username:
                logger.warning("LDAP directory search fallback failed: %s", exc)
            else:
                logger.info("LDAP supplement search failed: %s", exc)
    return list(by_username.values())


def _placeholder_email(username: str) -> str:
    domain = str(os.getenv("LDAP_DOMAIN") or "").strip() or "directory.local"
    return f"{username}@{domain}"


def _complete_user_representation(
    user: Dict[str, Any],
    *,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
) -> Dict[str, Any]:
    first = str(user.get("firstName") or "").strip()
    last = str(user.get("lastName") or "").strip()
    split_first, split_last = _split_full_name(full_name)
    first = first or split_first
    last = last or split_last
    username = str(user.get("username") or "user").strip() or "user"
    if not first:
        first = username
    if not last:
        last = "User"
    mail = str(email or user.get("email") or "").strip() or _placeholder_email(username)
    actions = [
        item
        for item in (user.get("requiredActions") or [])
        if item not in {"VERIFY_PROFILE", "VERIFY_EMAIL", "UPDATE_PROFILE"}
    ]
    return {
        "enabled": True,
        "email": mail,
        "emailVerified": True,
        "firstName": first,
        "lastName": last,
        "requiredActions": actions,
    }


def prepare_user_for_raptor_login(username: str) -> None:
    client = _client()
    user = client.find_user(username)
    if not user:
        return
    user_id = str(user["id"])
    try:
        client.update_user(user_id, _complete_user_representation(user))
    except KeycloakAdminError:
        actions = [
            item
            for item in (user.get("requiredActions") or [])
            if item not in {"VERIFY_PROFILE", "VERIFY_EMAIL", "UPDATE_PROFILE"}
        ]
        try:
            client.update_user(user_id, {"requiredActions": actions, "enabled": True})
        except KeycloakAdminError as exc:
            logger.warning("Could not clear profile required actions for %s: %s", username, exc)
    try:
        client.clear_brute_force(user_id)
    except KeycloakAdminError as exc:
        logger.warning("Could not clear Keycloak brute-force state for %s: %s", username, exc)


def auth_type_for_username(username: str) -> Optional[str]:
    try:
        client = _client()
        user = client.find_user(username)
        if not user:
            return None
        identities: List[Dict[str, Any]] = []
        providers: List[Dict[str, Any]] = []
        if not str(user.get("federationLink") or "").strip():
            try:
                identities = client.get_federated_identities(str(user["id"]))
            except Exception as exc:
                logger.debug("Could not read federated identities for %s: %s", username, exc)
            if identities:
                try:
                    providers = client.list_identity_providers()
                except Exception as exc:
                    logger.debug("Could not list identity providers: %s", exc)
        return auth_type_from_keycloak_user(user, identities, providers)
    except Exception as exc:
        logger.warning("Could not detect identity origin for %s: %s", username, exc)
        return None


def provision_ldap_user(
    username: str,
    email: str,
    role: str,
    permissions: List[str],
    full_name: Optional[str] = None,
) -> str:
    client = _client()
    user = client.find_user(username)
    if not user:
        raise LookupError(
            f"User {username} was not found in Keycloak. Search again after LDAP/IdP federation is connected."
        )
    user_id = str(user["id"])
    patch = _complete_user_representation(user, email=email, full_name=full_name)
    try:
        client.update_user(user_id, patch)
        user = client.get_user(user_id) or {**user, **patch, "id": user_id}
    except KeycloakAdminError as exc:
        logger.warning("Could not update federated user %s before allowlisting: %s", username, exc)
    identities: List[Dict[str, Any]] = []
    providers: List[Dict[str, Any]] = []
    try:
        identities = client.get_federated_identities(user_id)
    except Exception as exc:
        logger.debug("Could not read federated identities for %s: %s", username, exc)
    if identities:
        try:
            providers = client.list_identity_providers()
        except Exception as exc:
            logger.debug("Could not list identity providers: %s", exc)
    auth_type = auth_type_from_keycloak_user(user, identities, providers)
    if auth_type == "local":
        # Settings "Add LDAP Users" still stores directory-origin accounts as ldap
        # when Keycloak has not yet attached federationLink (import in progress).
        auth_type = "ldap"
    sanitized = assign_raptor_roles(client, user_id, role, permissions)
    upsert_identity_cache(
        username=username,
        email=str(patch.get("email") or email or ""),
        role=role,
        auth_type=auth_type,
        permissions_json=json.dumps(sanitized),
        is_service_account=0,
        full_name=full_name or _display_name(user),
        keycloak_id=user_id,
    )
    return user_id


def provision_sso_placeholder(
    username: str,
    email: str,
    role: str,
    permissions: List[str],
    auth_type: str = "oidc",
    full_name: Optional[str] = None,
) -> None:
    protocol = "saml" if str(auth_type or "").strip().lower() == "saml" else "oidc"
    client = _client()
    existing = client.find_user(username)
    sanitized = sanitize_extra_permissions(role, permissions or [])
    first_name, last_name = _split_full_name(full_name)
    created_new = False
    if existing:
        user_id = str(existing["id"])
        if existing.get("federationLink"):
            provision_ldap_user(username, email, role, permissions, full_name=full_name)
            return
    else:
        profile = _sso_placeholder_profile(username, full_name)
        if first_name:
            profile["firstName"] = first_name
        if last_name:
            profile["lastName"] = last_name
        user_id = client.create_user(
            {
                "username": username,
                "enabled": True,
                **profile,
            }
        )
        created_new = True
    try:
        assign_raptor_roles(client, user_id, role, permissions)
        add_allowed_user(
            username=username,
            email=email,
            role=role,
            auth_type=protocol,
            permissions_json=json.dumps(sanitized),
            is_service_account=0,
            full_name=full_name,
            keycloak_id=user_id,
        )
    except Exception:
        if created_new:
            try:
                client.delete_user(user_id)
            except Exception as exc:
                logger.error("Could not roll back SSO placeholder %s: %s", username, exc)
        raise


def revoke_unallowlisted_broker_user(keycloak_id: str, username: str = "") -> None:
    """Delete JIT Keycloak users that have no raptor-access after an SSO deny."""
    client = _client()
    user = None
    if str(keycloak_id or "").strip():
        user = client.get_user(str(keycloak_id).strip())
    if not user and username:
        user = client.find_user(username)
    if not user:
        return
    user_id = str(user.get("id") or "")
    if not user_id:
        return
    if str(user.get("federationLink") or "").strip():
        logger.info("SSO deny left LDAP user %s untouched", username or user_id)
        return
    role_names = {str(row.get("name") or "") for row in client.get_user_realm_roles(user_id)}
    if ACCESS_ROLE in role_names:
        logger.warning(
            "SSO deny for %s who already has raptor-access; leaving Keycloak user",
            username or user_id,
        )
        return
    try:
        client.delete_user(user_id)
        logger.info("Deleted Keycloak user %s after SSO deny (no raptor-access)", username or user_id)
        return
    except Exception as exc:
        logger.error("Could not delete denied broker user %s: %s", username or user_id, exc)
    try:
        client.update_user(user_id, {"enabled": False})
        logger.info("Disabled Keycloak user %s after SSO deny", username or user_id)
    except Exception as exc:
        logger.error("Could not disable denied broker user %s: %s", username or user_id, exc)


def provision_local_user(
    username: str,
    role: str,
    permissions: List[str],
    full_name: Optional[str] = None,
) -> Tuple[str, str]:
    client = _client()
    if client.find_user(username):
        raise ValueError(f"User {username} already exists in the system.")
    temp_password = secrets.token_urlsafe(12)
    if len(temp_password) < 12:
        temp_password = temp_password + secrets.token_urlsafe(12)
    temp_password = temp_password[:32]
    user_id = client.create_user(
        {
            "username": username,
            "enabled": True,
            "emailVerified": False,
            "firstName": (full_name or "").split(" ", 1)[0] if full_name else "",
            "lastName": (full_name or "").split(" ", 1)[1] if full_name and " " in full_name else "",
            "requiredActions": ["UPDATE_PASSWORD"],
        }
    )
    client.set_password(user_id, temp_password, temporary=True)
    sanitized = assign_raptor_roles(client, user_id, role, permissions)
    add_allowed_user(
        username=username,
        email="",
        role=role,
        auth_type="local",
        permissions_json=json.dumps(sanitized),
        is_service_account=0,
        full_name=full_name,
        keycloak_id=user_id,
    )
    return user_id, temp_password


def update_role(username: str, role: str) -> int:
    client = _client()
    user = client.find_user(username)
    if not user:
        return 0
    assign_raptor_roles(client, str(user["id"]), role, [])
    return update_user_role_repo(username, role, json.dumps([]))


def update_optional_permissions(username: str, permissions: List[str]) -> List[str]:
    client = _client()
    user = client.find_user(username)
    if not user:
        raise LookupError(username)
    role = get_user_role(username) or "user"
    sanitized = assign_raptor_roles(client, str(user["id"]), role, permissions)
    update_user_permissions_repo(username, json.dumps(sanitized))
    return sanitized


def delete_user(username: str) -> Tuple[Dict[str, Any], int]:
    client = _client()
    user = client.find_user(username)
    if user:
        client.delete_user(str(user["id"]))
    svc = get_service_account_by_username(username)
    if svc:
        client_row = client.get_client_by_client_id(service_client_id(username))
        if client_row:
            client.delete_client(str(client_row["id"]))
    try:
        remove_user_from_pentest_collaborations(username)
    except Exception as exc:
        logger.warning("Failed to remove '%s' from pentest collaborations before delete: %s", username, exc)
    return delete_identity(username)


def set_user_password(
    username: str,
    password: str,
    temporary: bool = False,
    *,
    relax_policy: bool = False,
) -> None:
    client = _client()
    user = client.find_user(username)
    if not user:
        raise LookupError(username)
    user_id = str(user["id"])
    original_policy = None
    if relax_policy:
        realm = client.get_realm() or {}
        original_policy = realm.get("passwordPolicy")
        realm["passwordPolicy"] = ""
        client.update_realm(realm)
    try:
        client.set_password(user_id, password, temporary=temporary)
    finally:
        if relax_policy and original_policy is not None:
            realm = client.get_realm() or {}
            realm["passwordPolicy"] = original_policy
            client.update_realm(realm)
    if not temporary:
        refreshed = client.get_user(user_id) or user
        actions = list(refreshed.get("requiredActions") or [])
        client.update_user(
            user_id,
            {"requiredActions": [item for item in actions if item != "UPDATE_PASSWORD"]},
        )
        try:
            client.clear_brute_force(user_id)
        except KeycloakAdminError as exc:
            logger.warning("Could not clear Keycloak brute-force state for %s: %s", username, exc)


def user_has_required_action(username: str, action: str = "UPDATE_PASSWORD") -> bool:
    client = _client()
    user = client.find_user(username)
    if not user:
        return False
    actions = user.get("requiredActions") or []
    return action in actions


def provision_service_account(username: str, full_name: Optional[str] = None) -> None:
    client = _client()
    client_id = service_client_id(username)
    if client.get_client_by_client_id(client_id):
        raise ValueError("Service account username already exists.")
    created = client.ensure_client(
        {
            "clientId": client_id,
            "name": f"RAPTOR service account {username}",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "standardFlowEnabled": False,
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": True,
            "frontchannelLogout": False,
            "fullScopeAllowed": False,
            "redirectUris": [],
            "webOrigins": [],
            "attributes": {
                "raptor.username": username,
            },
        }
    )
    client.ensure_service_scope_roles(str(created["id"]))
    create_service_account(username, keycloak_id=str(created["id"]), full_name=full_name)
    update_service_account_keycloak_client(username, str(created["id"]))


def push_service_account_credentials(
    username: str,
    api_key: str,
    scopes: List[str],
    expires_at: str,
) -> str:
    client = _client()
    kc_client = client.get_client_by_client_id(service_client_id(username))
    if not kc_client:
        raise LookupError(username)
    client_uuid = str(kc_client["id"])
    client.set_client_secret(client_uuid, api_key)
    attributes = dict(kc_client.get("attributes") or {})
    attributes["raptor.username"] = username
    attributes["raptor.expires_at"] = expires_at
    kc_client["attributes"] = attributes
    client.request("PUT", f"/clients/{client_uuid}", json=kc_client, expected=(204,))
    scope_roles = client.ensure_service_scope_roles(client_uuid)
    selected = [scope_roles[name] for name in scopes if name in scope_roles]
    service_user = client.find_user(f"service-account-{service_client_id(username)}")
    if service_user:
        client.replace_user_client_roles(str(service_user["id"]), client_uuid, selected)
    return client_uuid


def apply_service_account_scopes(username: str, scopes: List[str]) -> None:
    client = _client()
    kc_client = client.get_client_by_client_id(service_client_id(username))
    if not kc_client:
        raise LookupError(username)
    client_uuid = str(kc_client["id"])
    scope_roles = client.ensure_service_scope_roles(client_uuid)
    selected = [scope_roles[name] for name in scopes if name in scope_roles]
    service_user = client.find_user(f"service-account-{service_client_id(username)}")
    if service_user:
        client.replace_user_client_roles(str(service_user["id"]), client_uuid, selected)
    row = get_service_account_with_key(username)
    if row:
        update_service_account_scopes(int(row["service_account_id"]), json.dumps(scopes))


def verify_service_account_secret(client_id: str, secret: str, required_scope: str) -> bool:
    payload, status = client_credentials_grant(client_id, secret)
    if status != 200 or not payload:
        return False
    roles = payload.get("client_roles") or []
    return required_scope in roles


def migrate_interactive_user(client: KeycloakClient, row: Dict[str, Any], force_password_reset: bool) -> Optional[str]:
    username = str(row.get("username") or "").strip().lower()
    existing = client.find_user(username)
    full_name = row.get("full_name")
    temp_password = None
    if existing:
        user_id = str(existing["id"])
    else:
        user_id = client.create_user(
            {
                "username": username,
                "enabled": True,
                "email": row.get("email") or None,
                "emailVerified": bool(row.get("email")),
                "firstName": (full_name or "").split(" ", 1)[0] if full_name else "",
                "lastName": (full_name or "").split(" ", 1)[1] if full_name and " " in full_name else "",
                "requiredActions": ["UPDATE_PASSWORD"] if force_password_reset else [],
            }
        )
        if force_password_reset:
            temp_password = secrets.token_urlsafe(16)
            client.set_password(user_id, temp_password, temporary=True)
            logger.warning("Migrated local user '%s' with a new temporary Keycloak password.", username)
    role = str(row.get("role") or "user")
    permissions = row.get("permissions") or []
    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except json.JSONDecodeError:
            permissions = []
    assign_raptor_roles(client, user_id, role, permissions)
    update_user_keycloak_id(username, user_id)
    return temp_password


def migrate_service_account(client: KeycloakClient, row: Dict[str, Any]) -> Optional[str]:
    username = str(row.get("username") or "").strip().lower()
    client_id = service_client_id(username)
    created = client.ensure_client(
        {
            "clientId": client_id,
            "name": f"RAPTOR service account {username}",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": True,
            "fullScopeAllowed": False,
            "redirectUris": [],
            "webOrigins": [],
            "attributes": {"raptor.username": username},
        }
    )
    client.ensure_service_scope_roles(str(created["id"]))
    update_user_keycloak_id(username, str(created["id"]))
    update_service_account_keycloak_client(username, str(created["id"]))
    key_row = get_service_account_with_key(username)
    if key_row and key_row.get("has_api_key"):
        token = secrets.token_urlsafe(48)
        api_key = f"raptor_sk_{token}"[:256]
        client.set_client_secret(str(created["id"]), api_key)
        import hashlib

        fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        rotate_service_account_key(
            service_account_id=int(key_row["service_account_id"]),
            api_key=api_key,
            api_key_fingerprint=fingerprint,
            scopes_json=json.dumps(key_row.get("scopes") or []),
            rotated_at=str(key_row.get("key_created_at") or ""),
            expires_at=str(key_row.get("expires_at") or ""),
            actor_username="keycloak-migrator",
        )
        return api_key
    return None


def cache_from_login(
    username: str,
    role: str,
    extra_permissions: List[str],
    keycloak_id: str,
    auth_type: str,
    email: str = "",
) -> None:
    sanitized = sanitize_extra_permissions(role, extra_permissions)
    upsert_identity_cache(
        username=username,
        email=email or "",
        role=role,
        auth_type=auth_type if role != "admin" else "local",
        permissions_json=json.dumps(sanitized),
        is_service_account=0,
        full_name=None,
        keycloak_id=keycloak_id,
        skip_admin=True,
    )


__all__ = [
    "apply_service_account_scopes",
    "assign_raptor_roles",
    "auth_type_for_username",
    "auth_type_from_keycloak_user",
    "cache_from_login",
    "delete_user",
    "migrate_interactive_user",
    "migrate_service_account",
    "prepare_user_for_raptor_login",
    "provision_ldap_user",
    "provision_local_user",
    "provision_service_account",
    "provision_sso_placeholder",
    "push_service_account_credentials",
    "revoke_unallowlisted_broker_user",
    "search_directory_users",
    "set_user_password",
    "update_optional_permissions",
    "update_role",
    "user_has_required_action",
    "verify_service_account_secret",
]
