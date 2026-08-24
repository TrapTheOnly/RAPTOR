import hashlib
import logging
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode
from uuid import uuid4

from app.http.request_utils import normalize_auth_key
from app.integrations.keycloak.client import (
    authorization_code_grant,
    decode_access_token,
    end_session,
    refresh_token_grant,
)
from app.integrations.keycloak.constants import (
    ACCESS_ROLE,
    LOGIN_CLIENT_ID,
    REALM,
    is_supported_sso_provider,
    keycloak_base_url,
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
from app.services.keycloak_identity_service import assign_raptor_roles, cache_from_login, revoke_unallowlisted_broker_user
from app.services.session_policy_service import initialize_session_tracking

logger = logging.getLogger(__name__)

_PUBLIC_SSO_ERROR = "failed"
_JWKS_CACHE: Dict[str, Any] = {"fetched_at": 0.0, "keys": []}
_JWKS_TTL_SECONDS = 300

_LOGIN_ERROR_MESSAGES = {
    "failed": "Sign-in failed. Try again.",
    "not_allowlisted": "Sign-in failed. Try again.",
    "invalid_state": "Sign-in failed. Try again.",
    "idp_unavailable": "Sign-in failed. Try again.",
    "access_denied": "Sign-in failed. Try again.",
    "unsupported": "Sign-in failed. Try again.",
}


def login_error_message(code: str) -> str:
    return _LOGIN_ERROR_MESSAGES.get(str(code or "").strip(), "Sign-in failed. Try again.")


def public_sso_error(_code: Optional[str] = None) -> str:
    """Never put allowlist or internal reasons in the login URL."""
    return _PUBLIC_SSO_ERROR


def _b64url_decode(data: str) -> bytes:
    import base64

    padded = str(data or "") + "=" * (-len(str(data or "")) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _expected_issuers() -> Tuple[str, ...]:
    return (
        f"{keycloak_public_url()}/realms/{REALM}",
        f"{keycloak_base_url()}/realms/{REALM}",
    )


def _id_token_claims_valid(claims: Dict[str, Any], expected_nonce: str) -> bool:
    if not isinstance(claims, dict) or not claims:
        return False
    if not expected_nonce or str(claims.get("nonce") or "") != expected_nonce:
        return False
    issuer = str(claims.get("iss") or "").rstrip("/")
    if issuer not in {item.rstrip("/") for item in _expected_issuers()}:
        return False
    audience = claims.get("aud")
    if isinstance(audience, str):
        audience = [audience]
    if not isinstance(audience, list) or LOGIN_CLIENT_ID not in {str(item) for item in audience}:
        return False
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or float(exp) <= time.time() - 30:
        return False
    return True


def _fetch_jwks_keys() -> list:
    now = time.time()
    cached_keys = _JWKS_CACHE.get("keys") or []
    if cached_keys and now - float(_JWKS_CACHE.get("fetched_at") or 0) < _JWKS_TTL_SECONDS:
        return list(cached_keys)
    import httpx

    url = f"{keycloak_base_url()}/realms/{REALM}/protocol/openid-connect/certs"
    try:
        response = httpx.get(url, timeout=10.0)
        payload = response.json() if response.status_code == 200 else {}
    except Exception as exc:
        logger.warning("Could not fetch Keycloak JWKS: %s", exc)
        return list(cached_keys)
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list):
        return list(cached_keys)
    _JWKS_CACHE["keys"] = keys
    _JWKS_CACHE["fetched_at"] = now
    return list(keys)


def _id_token_signature_valid(id_token: str) -> bool:
    parts = str(id_token or "").split(".")
    if len(parts) != 3:
        return False
    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if str(header.get("alg") or "") != "RS256":
        return False
    kid = str(header.get("kid") or "")
    keys = _fetch_jwks_keys()
    jwk = next((row for row in keys if isinstance(row, dict) and str(row.get("kid") or "") == kid), None)
    if not jwk and len(keys) == 1 and isinstance(keys[0], dict):
        jwk = keys[0]
    if not jwk:
        return False
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

        n = int.from_bytes(_b64url_decode(str(jwk.get("n") or "")), "big")
        e = int.from_bytes(_b64url_decode(str(jwk.get("e") or "")), "big")
        public_key = RSAPublicNumbers(e, n).public_key(default_backend())
        public_key.verify(
            _b64url_decode(parts[2]),
            f"{parts[0]}.{parts[1]}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception as exc:
        logger.warning("SSO id_token signature check failed: %s", exc)
        return False


def verify_oidc_id_token(id_token: str, expected_nonce: str) -> bool:
    claims = decode_access_token(id_token)
    if not _id_token_claims_valid(claims, expected_nonce):
        return False
    if not _id_token_signature_valid(id_token):
        return False
    return True


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
        return False
    try:
        row = get_session_tokens(session_key)
    except Exception as exc:
        logger.warning("Could not read Keycloak session tokens: %s", exc)
        return False
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


def _deny_sso(
    reason: str,
    *,
    username: str = "",
    keycloak_id: str = "",
    revoke: bool = False,
) -> Tuple[str, str]:
    logger.warning("SSO denied (%s) user=%s sub=%s", reason, username or "-", keycloak_id or "-")
    if revoke:
        try:
            revoke_unallowlisted_broker_user(keycloak_id, username)
        except Exception as exc:
            logger.error("Could not revoke denied broker user %s: %s", username or keycloak_id, exc)
    return "/login", reason


def complete_sso_callback(session_obj: Any, args: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    if args.get("error"):
        return _deny_sso("access_denied")
    expected_state = str(session_obj.get("sso_state") or "")
    expected_nonce = str(session_obj.get("sso_nonce") or "")
    state = str(args.get("state") or "")
    code = str(args.get("code") or "")
    verifier = str(session_obj.get("sso_code_verifier") or "")
    alias = str(session_obj.get("sso_alias") or "")
    redirect_uri = str(session_obj.get("sso_redirect_uri") or sso_callback_url())
    if not expected_state or not state or state != expected_state or not code or not verifier:
        return _deny_sso("invalid_state")
    grant = authorization_code_grant(code, redirect_uri, verifier)
    session_obj.pop("sso_state", None)
    session_obj.pop("sso_nonce", None)
    session_obj.pop("sso_code_verifier", None)
    session_obj.pop("sso_alias", None)
    session_obj.pop("sso_redirect_uri", None)
    if grant.get("status") != "ok":
        return _deny_sso("idp_unavailable")
    id_token = str(grant.get("id_token") or "")
    if not verify_oidc_id_token(id_token, expected_nonce):
        return _deny_sso("invalid_state")
    claims = grant.get("id_claims") or grant.get("claims") or {}
    preferred = normalize_auth_key(
        claims.get("preferred_username") or claims.get("username") or claims.get("email")
    )
    keycloak_id = str(claims.get("sub") or "")
    allowlist = find_sso_allowlist(preferred, keycloak_id=keycloak_id)
    if not allowlist or allowlist.get("is_service_account"):
        return _deny_sso("not_allowlisted", username=preferred, keycloak_id=keycloak_id, revoke=True)
    username = allowlist["username"]
    if username == ADMIN_USERNAME:
        return _deny_sso("not_allowlisted", username=username, keycloak_id=keycloak_id, revoke=True)
    realm_roles = list(grant.get("realm_roles") or [])
    if ACCESS_ROLE not in realm_roles or not allowlist.get("keycloak_id"):
        try:
            from app.integrations.keycloak.client import KeycloakClient
            from app.repositories.users_repository import update_user_keycloak_id

            client = KeycloakClient()
            user = client.get_user(keycloak_id) if keycloak_id else client.find_user(preferred or username)
            if not user:
                return _deny_sso("not_allowlisted", username=username, keycloak_id=keycloak_id, revoke=True)
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
                return _deny_sso("not_allowlisted", username=username, keycloak_id=keycloak_id)
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
    "public_sso_error",
    "verify_oidc_id_token",
]
