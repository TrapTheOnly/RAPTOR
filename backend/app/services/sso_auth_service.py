import hashlib
import logging
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode
from uuid import uuid4

from app.http.request_utils import normalize_auth_key
from app.integrations.keycloak.client import (
    authorization_code_grant,
    end_session,
    refresh_token_grant,
)
from app.integrations.keycloak.constants import (
    ACCESS_ROLE,
    LOGIN_CLIENT_ID,
    REALM,
    is_supported_sso_provider,
    keycloak_public_url,
    role_from_realm_roles,
    sso_callback_url,
)
from app.repositories.admin_users_repository import ADMIN_USERNAME
from app.repositories.sso_token_repository import (
    delete_session_tokens,
    get_session_tokens,
    upsert_session_tokens,
)
from app.repositories.users_repository import find_sso_allowlist
from app.services.keycloak_identity_service import assign_raptor_roles, cache_from_login
from app.services.session_policy_service import initialize_session_tracking

logger = logging.getLogger(__name__)

_LOGIN_ERROR_MESSAGES = {
    "not_allowlisted": "This account is not allowed to sign in to RAPTOR.",
    "invalid_state": "Sign-in could not be completed. Try again.",
    "idp_unavailable": "The identity provider is unavailable.",
    "access_denied": "Sign-in was cancelled or denied.",
    "unsupported": "That sign-in method is not supported.",
}


def login_error_message(code: str) -> str:
    return _LOGIN_ERROR_MESSAGES.get(str(code or "").strip(), "Sign-in failed. Try again.")


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    import base64

    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorization_url(alias: str, session_obj: Any) -> Tuple[Optional[str], Optional[str]]:
    from app.integrations.keycloak.client import KeycloakClient

    alias = str(alias or "").strip()
    if not alias:
        return None, "unsupported"
    try:
        client = KeycloakClient()
        provider = client.get_identity_provider(alias)
    except Exception as exc:
        logger.error("Could not load SSO provider %s: %s", alias, exc)
        return None, "idp_unavailable"
    if not provider or not provider.get("enabled"):
        return None, "unsupported"
    if not is_supported_sso_provider(str(provider.get("providerId") or "")):
        return None, "unsupported"
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    session_obj["sso_state"] = state
    session_obj["sso_nonce"] = nonce
    session_obj["sso_code_verifier"] = verifier
    session_obj["sso_alias"] = alias
    session_obj["sso_redirect_uri"] = sso_callback_url()
    query = urlencode(
        {
            "client_id": LOGIN_CLIENT_ID,
            "redirect_uri": sso_callback_url(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
            "kc_idp_hint": alias,
        }
    )
    return f"{keycloak_public_url()}/realms/{REALM}/protocol/openid-connect/auth?{query}", None


def _parse_permissions(raw: Any) -> list:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except ValueError:
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return []


def _store_tokens(session_obj: Any, username: str, grant: Dict[str, Any]) -> None:
    access = str(grant.get("access_token") or "")
    if not access:
        return
    session_key = str(session_obj.get("kc_session_key") or uuid4())
    expires_in = int(grant.get("expires_in") or 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(30, expires_in))
    try:
        upsert_session_tokens(
            session_key,
            username,
            access,
            str(grant.get("refresh_token") or ""),
            expires_at,
        )
    except Exception as exc:
        logger.warning("Could not persist Keycloak tokens for %s: %s", username, exc)
        return
    session_obj["kc_session_key"] = session_key


def attach_grant_tokens(session_obj: Any, username: str, grant: Dict[str, Any]) -> None:
    _store_tokens(session_obj, username, grant)


def identity_session_valid(session_obj: Any) -> bool:
    if not session_obj.get("logged_in"):
        return True
    session_key = str(session_obj.get("kc_session_key") or "").strip()
    if not session_key:
        return True
    try:
        row = get_session_tokens(session_key)
    except Exception as exc:
        logger.warning("Could not read Keycloak session tokens: %s", exc)
        return True
    if not row:
        return False
    expires_at = row.get("access_expires_at")
    now = datetime.now(timezone.utc)
    if isinstance(expires_at, datetime) and expires_at > now + timedelta(seconds=30):
        return True
    refresh = str(row.get("refresh_token") or "").strip()
    if not refresh:
        delete_session_tokens(session_key)
        return False
    grant = refresh_token_grant(refresh)
    if grant.get("status") != "ok":
        delete_session_tokens(session_key)
        return False
    username = str(session_obj.get("username") or row.get("username") or "")
    realm_roles = grant.get("realm_roles") or []
    if ACCESS_ROLE not in realm_roles and username != ADMIN_USERNAME:
        delete_session_tokens(session_key)
        return False
    _store_tokens(session_obj, username, grant)
    return True


def drop_invalid_identity_session(session_obj: Any) -> bool:
    if not session_obj.get("logged_in"):
        return False
    if identity_session_valid(session_obj):
        return False
    clear_identity_session(session_obj)
    session_obj.clear()
    return True


def clear_identity_session(session_obj: Any) -> None:
    session_key = str(session_obj.get("kc_session_key") or "").strip()
    refresh = ""
    if session_key:
        row = delete_session_tokens(session_key)
        if row:
            refresh = str(row.get("refresh_token") or "")
    if refresh:
        end_session(refresh)
    session_obj.pop("kc_session_key", None)
    session_obj.pop("sso_state", None)
    session_obj.pop("sso_nonce", None)
    session_obj.pop("sso_code_verifier", None)
    session_obj.pop("sso_alias", None)
    session_obj.pop("sso_redirect_uri", None)


def _establish(session_obj: Any, username: str, role: str, grant: Dict[str, Any], auth_type: str) -> None:
    extra = grant.get("client_roles") or []
    claims = grant.get("claims") or {}
    keycloak_id = str(claims.get("sub") or "")
    email = str(claims.get("email") or "")
    session_obj.clear()
    session_obj.permanent = True
    session_obj["username"] = username
    session_obj["user_type"] = role
    session_obj["logged_in"] = True
    session_obj.pop("reset_required", None)
    initialize_session_tracking()
    attach_grant_tokens(session_obj, username, grant)
    if role != "admin":
        cache_from_login(username, role, extra, keycloak_id, auth_type, email=email)


def complete_sso_callback(session_obj: Any, args: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    if args.get("error"):
        return "/login", "access_denied"
    expected_state = str(session_obj.get("sso_state") or "")
    state = str(args.get("state") or "")
    code = str(args.get("code") or "")
    verifier = str(session_obj.get("sso_code_verifier") or "")
    alias = str(session_obj.get("sso_alias") or "")
    redirect_uri = str(session_obj.get("sso_redirect_uri") or sso_callback_url())
    if not expected_state or not state or state != expected_state or not code or not verifier:
        return "/login", "invalid_state"
    grant = authorization_code_grant(code, redirect_uri, verifier)
    session_obj.pop("sso_state", None)
    session_obj.pop("sso_nonce", None)
    session_obj.pop("sso_code_verifier", None)
    session_obj.pop("sso_alias", None)
    session_obj.pop("sso_redirect_uri", None)
    if grant.get("status") != "ok":
        return "/login", "idp_unavailable"
    claims = grant.get("claims") or {}
    preferred = normalize_auth_key(claims.get("preferred_username") or claims.get("username"))
    email = str(claims.get("email") or "").strip().lower()
    keycloak_id = str(claims.get("sub") or "")
    allowlist = find_sso_allowlist(preferred, email)
    if not allowlist or allowlist.get("is_service_account"):
        return "/login", "not_allowlisted"
    username = allowlist["username"]
    if username == ADMIN_USERNAME:
        return "/login", "not_allowlisted"
    realm_roles = list(grant.get("realm_roles") or [])
    if ACCESS_ROLE not in realm_roles or not allowlist.get("keycloak_id"):
        try:
            from app.integrations.keycloak.client import KeycloakClient
            from app.repositories.users_repository import update_user_keycloak_id

            client = KeycloakClient()
            user = client.get_user(keycloak_id) if keycloak_id else client.find_user(preferred or username)
            if not user:
                return "/login", "not_allowlisted"
            if ACCESS_ROLE not in realm_roles:
                assign_raptor_roles(
                    client,
                    str(user["id"]),
                    allowlist["role"],
                    _parse_permissions(allowlist.get("permissions")),
                )
                realm_roles.append(ACCESS_ROLE)
            update_user_keycloak_id(username, str(user["id"]))
        except Exception as exc:
            logger.error("Could not link pre-provisioned SSO user %s: %s", username, exc)
            if ACCESS_ROLE not in realm_roles:
                return "/login", "not_allowlisted"
    role = allowlist.get("role") or role_from_realm_roles(realm_roles)
    auth_type = allowlist.get("auth_type") or "oidc"
    if auth_type in {"local", "ldap", "service"}:
        auth_type = "saml" if str(alias).find("saml") >= 0 else "oidc"
    _establish(session_obj, username, role, grant, auth_type)
    from app.services.audit_service import record_audit_event

    record_audit_event(
        actor=username,
        actor_type="user",
        action="auth.login",
        entity_type="user",
        entity_id=username,
        metadata={"method": "sso", "alias": alias},
    )
    return "/", None


__all__ = [
    "attach_grant_tokens",
    "authorization_url",
    "clear_identity_session",
    "complete_sso_callback",
    "drop_invalid_identity_session",
    "identity_session_valid",
    "login_error_message",
]
