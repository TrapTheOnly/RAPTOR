import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.integrations.keycloak.client import KeycloakAdminError, KeycloakClient
from app.integrations.keycloak.constants import (
    REALM,
    is_supported_sso_provider,
    keycloak_public_url,
    sso_callback_url,
    sso_protocol,
)

logger = logging.getLogger(__name__)

_ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_SUPPORTED_CREATE = frozenset({"oidc", "saml"})


def _client() -> KeycloakClient:
    return KeycloakClient()


def _secret_present(config: Dict[str, Any]) -> bool:
    secret = str(config.get("clientSecret") or "").strip()
    return bool(secret) and secret != "**********"


def connection_public_view(representation: Dict[str, Any]) -> Dict[str, Any]:
    config = dict(representation.get("config") or {}) if isinstance(representation.get("config"), dict) else {}
    provider_id = str(representation.get("providerId") or "").strip().lower()
    protocol = sso_protocol(provider_id)
    alias = str(representation.get("alias") or "").strip()
    acs_url = ""
    if protocol == "saml" and alias:
        acs_url = f"{keycloak_public_url()}/realms/{REALM}/broker/{alias}/endpoint"
    return {
        "alias": alias,
        "display_name": str(representation.get("displayName") or alias).strip() or alias,
        "protocol": protocol,
        "enabled": bool(representation.get("enabled")),
        "has_client_secret": _secret_present(config),
        "issuer": str(config.get("issuer") or "").strip(),
        "authorization_url": str(config.get("authorizationUrl") or "").strip(),
        "token_url": str(config.get("tokenUrl") or "").strip(),
        "jwks_url": str(config.get("jwksUrl") or "").strip(),
        "logout_url": str(config.get("logoutUrl") or config.get("singleLogoutServiceUrl") or "").strip(),
        "client_id": str(config.get("clientId") or "").strip(),
        "entity_id": str(config.get("entityId") or "").strip(),
        "sso_url": str(config.get("singleSignOnServiceUrl") or "").strip(),
        "metadata_url": str(config.get("metadataDescriptorUrl") or "").strip(),
        "acs_url": acs_url,
        "redirect_uri": sso_callback_url(),
    }


def _supported_rows(client: KeycloakClient) -> List[Dict[str, Any]]:
    rows = []
    for row in client.list_identity_providers():
        if is_supported_sso_provider(str(row.get("providerId") or "")):
            rows.append(row)
    return rows


def list_connections() -> Tuple[Dict[str, Any], int]:
    try:
        client = _client()
        connections = [connection_public_view(row) for row in _supported_rows(client)]
        connections.sort(key=lambda item: str(item.get("display_name") or item.get("alias") or "").lower())
        return {"connections": connections, "redirect_uri": sso_callback_url()}, 200
    except KeycloakAdminError as exc:
        logger.error("Failed to list SSO connections: %s", exc)
        return {"error": "Could not load SSO connections."}, 502


def list_login_providers() -> Tuple[Dict[str, Any], int]:
    payload, status = list_connections()
    if status != 200:
        return {"providers": []}, 200
    providers = [
        {
            "alias": row["alias"],
            "display_name": row["display_name"],
            "protocol": row["protocol"],
        }
        for row in payload.get("connections") or []
        if row.get("enabled") and row.get("alias")
    ]
    return {"providers": providers}, 200


def get_connection(alias: str) -> Tuple[Dict[str, Any], int]:
    try:
        client = _client()
        row = client.get_identity_provider(alias)
    except KeycloakAdminError as exc:
        logger.error("Failed to load SSO connection %s: %s", alias, exc)
        return {"error": "Could not load SSO connection."}, 502
    if not row or not is_supported_sso_provider(str(row.get("providerId") or "")):
        return {"error": "SSO connection not found."}, 404
    return {"connection": connection_public_view(row)}, 200


def _normalize_alias(raw: str) -> str:
    return str(raw or "").strip().lower()


def _validate_alias(alias: str) -> Optional[str]:
    if not _ALIAS_RE.match(alias):
        return "Alias must be lowercase letters, numbers, and hyphens."
    return None


def _representation_from_payload(data: Dict[str, Any], *, existing: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    protocol = str(data.get("protocol") or "").strip().lower()
    if protocol == "keycloak-oidc":
        protocol = "oidc"
    if protocol not in _SUPPORTED_CREATE:
        return None, "Protocol must be oidc or saml."
    alias = _normalize_alias(data.get("alias"))
    if existing:
        alias = str(existing.get("alias") or alias).strip()
    error = _validate_alias(alias)
    if error:
        return None, error
    display = str(data.get("display_name") or alias).strip() or alias
    enabled = data.get("enabled")
    if enabled is None:
        enabled = True if not existing else bool(existing.get("enabled"))
    config: Dict[str, str] = {
        "syncMode": "IMPORT",
        "trustEmail": "true",
        "hideOnLoginPage": "true",
        "guiOrder": "0",
    }
    if existing and isinstance(existing.get("config"), dict):
        for key, value in existing["config"].items():
            if value is None:
                continue
            config[str(key)] = str(value)
    if protocol == "oidc":
        client_id = str(data.get("client_id") or config.get("clientId") or "").strip()
        if not client_id:
            return None, "Client ID is required."
        issuer = str(data.get("issuer") or "").strip()
        authorization_url = str(data.get("authorization_url") or "").strip()
        token_url = str(data.get("token_url") or "").strip()
        if not issuer and not (authorization_url and token_url):
            return None, "Issuer or authorization and token URLs are required."
        config.update(
            {
                "clientId": client_id,
                "defaultScope": str(data.get("default_scope") or config.get("defaultScope") or "openid email profile"),
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
        jwks_url = str(data.get("jwks_url") or "").strip()
        if jwks_url:
            config["jwksUrl"] = jwks_url
        logout_url = str(data.get("logout_url") or "").strip()
        if logout_url:
            config["logoutUrl"] = logout_url
        secret = str(data.get("client_secret") or "").strip()
        if secret:
            config["clientSecret"] = secret
        elif not existing:
            return None, "Client secret is required."
        else:
            config.pop("clientSecret", None)
    else:
        entity_id = str(data.get("entity_id") or config.get("entityId") or "").strip()
        sso_url = str(data.get("sso_url") or config.get("singleSignOnServiceUrl") or "").strip()
        metadata_url = str(data.get("metadata_url") or "").strip()
        if metadata_url:
            config["metadataDescriptorUrl"] = metadata_url
        if not entity_id or not sso_url:
            return None, "SAML entity ID and SSO URL are required."
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
        logout_url = str(data.get("logout_url") or "").strip()
        if logout_url:
            config["singleLogoutServiceUrl"] = logout_url
    body = {
        "alias": alias,
        "displayName": display,
        "providerId": protocol,
        "enabled": bool(enabled),
        "updateProfileFirstLoginMode": "off",
        "trustEmail": True,
        "storeToken": False,
        "linkOnly": False,
        "firstBrokerLoginFlowAlias": "first broker login",
        "config": config,
    }
    return body, None


def create_connection(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    body, error = _representation_from_payload(data or {})
    if error:
        return {"error": error}, 400
    alias = str(body["alias"])
    try:
        client = _client()
        if client.get_identity_provider(alias):
            return {"error": f"SSO connection '{alias}' already exists."}, 409
        created = client.ensure_identity_provider(body)
        return {"connection": connection_public_view(created), "message": "SSO connection created."}, 201
    except KeycloakAdminError as exc:
        logger.error("Failed to create SSO connection %s: %s", alias, exc)
        return {"error": "Could not create SSO connection."}, 502


def update_connection(alias: str, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    try:
        client = _client()
        existing = client.get_identity_provider(alias)
    except KeycloakAdminError as exc:
        logger.error("Failed to load SSO connection %s: %s", alias, exc)
        return {"error": "Could not update SSO connection."}, 502
    if not existing or not is_supported_sso_provider(str(existing.get("providerId") or "")):
        return {"error": "SSO connection not found."}, 404
    payload = dict(data or {})
    payload["alias"] = alias
    payload.setdefault("protocol", sso_protocol(str(existing.get("providerId") or "")))
    body, error = _representation_from_payload(payload, existing=existing)
    if error:
        return {"error": error}, 400
    try:
        updated = client.ensure_identity_provider(body)
        return {"connection": connection_public_view(updated), "message": "SSO connection saved."}, 200
    except KeycloakAdminError as exc:
        logger.error("Failed to update SSO connection %s: %s", alias, exc)
        return {"error": "Could not update SSO connection."}, 502


def delete_connection(alias: str) -> Tuple[Dict[str, Any], int]:
    try:
        client = _client()
        existing = client.get_identity_provider(alias)
        if not existing or not is_supported_sso_provider(str(existing.get("providerId") or "")):
            return {"error": "SSO connection not found."}, 404
        client.delete_identity_provider(alias)
        return {"message": f"SSO connection '{alias}' deleted."}, 200
    except KeycloakAdminError as exc:
        logger.error("Failed to delete SSO connection %s: %s", alias, exc)
        return {"error": "Could not delete SSO connection."}, 502


def test_connection(alias: str) -> Tuple[Dict[str, Any], int]:
    payload, status = get_connection(alias)
    if status != 200:
        return payload, status
    connection = payload["connection"]
    protocol = connection.get("protocol")
    import httpx

    try:
        if protocol == "oidc":
            issuer = str(connection.get("issuer") or "").rstrip("/")
            if issuer:
                url = f"{issuer}/.well-known/openid-configuration"
                response = httpx.get(url, timeout=10.0)
                if response.status_code >= 400:
                    return {"error": f"OIDC discovery failed ({response.status_code})."}, 400
                return {"message": "OIDC discovery succeeded."}, 200
            if connection.get("authorization_url") and connection.get("token_url"):
                return {"message": "OIDC endpoints are set. Discovery URL was not provided."}, 200
            return {"error": "OIDC issuer or authorization/token URLs are missing."}, 400
        metadata_url = str(connection.get("metadata_url") or connection.get("sso_url") or "").strip()
        if not metadata_url:
            return {"error": "SAML metadata or SSO URL is missing."}, 400
        response = httpx.get(metadata_url, timeout=10.0)
        if response.status_code >= 400:
            return {"error": f"SAML endpoint failed ({response.status_code})."}, 400
        return {"message": "SAML endpoint is reachable."}, 200
    except httpx.HTTPError as exc:
        logger.warning("SSO connection test failed for %s: %s", alias, exc)
        return {"error": "Could not reach the identity provider."}, 400


__all__ = [
    "connection_public_view",
    "create_connection",
    "delete_connection",
    "get_connection",
    "list_connections",
    "list_login_providers",
    "test_connection",
    "update_connection",
]
