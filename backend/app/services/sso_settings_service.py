import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree

from app.integrations.keycloak.client import KeycloakAdminError, KeycloakClient
from app.integrations.keycloak.constants import (
    FIRST_BROKER_FLOW,
    REALM,
    broker_endpoint_url,
    broker_sp_metadata_url,
    is_supported_sso_provider,
    keycloak_base_url,
    realm_issuer_url,
    sso_callback_url,
    sso_protocol,
    sso_start_url,
)

logger = logging.getLogger(__name__)

_ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_SUPPORTED_CREATE = frozenset({"oidc", "saml"})
_SAML_HTTP_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
_SAML_HTTP_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"


def _xml_local_name(tag: str) -> str:
    return str(tag or "").rsplit("}", 1)[-1]


def _xml_find(element: ElementTree.Element, name: str) -> Optional[ElementTree.Element]:
    if _xml_local_name(element.tag) == name:
        return element
    for child in list(element):
        found = _xml_find(child, name)
        if found is not None:
            return found
    return None


def _xml_findall(element: ElementTree.Element, name: str) -> List[ElementTree.Element]:
    matches = []
    if _xml_local_name(element.tag) == name:
        matches.append(element)
    for child in list(element):
        matches.extend(_xml_findall(child, name))
    return matches


def parse_saml_idp_metadata(xml_text: str) -> Dict[str, str]:
    """Read IdP entity ID and SSO/logout URLs from a SAML metadata document."""
    parsed: Dict[str, str] = {}
    text = str(xml_text or "").strip()
    if not text:
        return parsed
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return parsed
    descriptor = _xml_find(root, "EntityDescriptor")
    if descriptor is None:
        descriptor = root
    entity_id = str(descriptor.get("entityID") or "").strip()
    if entity_id:
        parsed["entity_id"] = entity_id
    idp = _xml_find(descriptor, "IDPSSODescriptor")
    if idp is None:
        return parsed
    if str(idp.get("WantAuthnRequestsSigned") or "").strip().lower() == "true":
        parsed["want_authn_requests_signed"] = "true"
    sso_post = ""
    sso_redirect = ""
    for service in _xml_findall(idp, "SingleSignOnService"):
        binding = str(service.get("Binding") or "").strip()
        location = str(service.get("Location") or "").strip()
        if not location:
            continue
        if binding == _SAML_HTTP_POST and not sso_post:
            sso_post = location
        elif binding == _SAML_HTTP_REDIRECT and not sso_redirect:
            sso_redirect = location
    sso_url = sso_post or sso_redirect
    if sso_url:
        parsed["sso_url"] = sso_url
    for service in _xml_findall(idp, "SingleLogoutService"):
        location = str(service.get("Location") or "").strip()
        if location:
            parsed["logout_url"] = location
            break
    return parsed


def _hydrate_saml_from_metadata(config: Dict[str, Any], metadata_url: str) -> None:
    """Keycloak 26 does not copy SSO URL from metadata into the broker config."""
    url = str(metadata_url or "").strip()
    if not url:
        return
    import httpx

    try:
        response = httpx.get(url, timeout=10.0)
    except httpx.HTTPError as exc:
        logger.warning("Could not fetch SAML metadata %s: %s", url, exc)
        return
    if response.status_code >= 400:
        logger.warning("SAML metadata %s returned %s", url, response.status_code)
        return
    parsed = parse_saml_idp_metadata(response.text)
    # Keycloak SAML broker: entityId is THIS Keycloak's SP issuer.
    # The remote IdP entity ID belongs in idpEntityId.
    if parsed.get("entity_id") and not str(config.get("idpEntityId") or "").strip():
        config["idpEntityId"] = parsed["entity_id"]
    if parsed.get("sso_url"):
        config["singleSignOnServiceUrl"] = parsed["sso_url"]
    if parsed.get("logout_url") and not str(config.get("singleLogoutServiceUrl") or "").strip():
        config["singleLogoutServiceUrl"] = parsed["logout_url"]
    if parsed.get("want_authn_requests_signed") == "true":
        config["wantAuthnRequestsSigned"] = "true"


def _client() -> KeycloakClient:
    return KeycloakClient()


def _secret_present(config: Dict[str, Any]) -> bool:
    secret = str(config.get("clientSecret") or "").strip()
    return bool(secret) and secret != "**********"


def _first_broker_flow_alias(client: KeycloakClient) -> str:
    try:
        alias = client.ensure_raptor_first_broker_flow()
    except Exception as exc:
        logger.warning("Could not ensure RAPTOR first-broker flow: %s", exc)
        return "first broker login"
    return alias or "first broker login"


def connection_public_view(representation: Dict[str, Any]) -> Dict[str, Any]:
    config = dict(representation.get("config") or {}) if isinstance(representation.get("config"), dict) else {}
    provider_id = str(representation.get("providerId") or "").strip().lower()
    protocol = sso_protocol(provider_id)
    alias = str(representation.get("alias") or "").strip()
    broker = broker_endpoint_url(alias) if alias else ""
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
        "entity_id": str(config.get("idpEntityId") or "").strip(),
        "sso_url": str(config.get("singleSignOnServiceUrl") or "").strip(),
        "metadata_url": str(config.get("metadataDescriptorUrl") or "").strip(),
        "acs_url": broker,
        "broker_redirect_uri": broker,
        "sp_entity_id": realm_issuer_url(),
        "start_url": sso_start_url(alias) if alias else "",
        "sp_metadata_url": broker_sp_metadata_url(alias) if protocol == "saml" and alias else "",
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
        if "accounts.google.com" in " ".join((issuer, authorization_url, str(config.get("issuer") or ""))):
            config["principalType"] = "ATTRIBUTE"
            config["principalAttribute"] = "email"
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
        entity_id = str(data.get("entity_id") or config.get("idpEntityId") or "").strip()
        sso_url = str(data.get("sso_url") or config.get("singleSignOnServiceUrl") or "").strip()
        metadata_url = str(data.get("metadata_url") or config.get("metadataDescriptorUrl") or "").strip()
        if metadata_url:
            config["metadataDescriptorUrl"] = metadata_url
            config["useMetadataDescriptorUrl"] = "true"
            _hydrate_saml_from_metadata(config, metadata_url)
            entity_id = entity_id or str(config.get("idpEntityId") or "").strip()
            sso_url = sso_url or str(config.get("singleSignOnServiceUrl") or "").strip()
        elif config.get("useMetadataDescriptorUrl") and not metadata_url:
            config.pop("useMetadataDescriptorUrl", None)
        if not metadata_url and (not entity_id or not sso_url):
            return None, "SAML IdP metadata URL or IdP entity ID and IdP SSO URL are required."
        config.update(
            {
                "nameIDPolicyFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
                "principalType": "SUBJECT",
                "wantAuthnRequestsSigned": str(config.get("wantAuthnRequestsSigned") or "false"),
                "postBindingAuthnRequest": "true",
                "postBindingResponse": "true",
                "entityId": realm_issuer_url(),
            }
        )
        if entity_id:
            config["idpEntityId"] = entity_id
        if sso_url:
            config["singleSignOnServiceUrl"] = sso_url
        logout_url = str(data.get("logout_url") or config.get("singleLogoutServiceUrl") or "").strip()
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
        "firstBrokerLoginFlowAlias": FIRST_BROKER_FLOW,
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
        body["firstBrokerLoginFlowAlias"] = _first_broker_flow_alias(client)
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
        body["firstBrokerLoginFlowAlias"] = _first_broker_flow_alias(client)
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


def _discovery_from_oidc_endpoint(url: str) -> str:
    raw = str(url or "").strip().split("?", 1)[0]
    if not raw:
        return ""
    marker = "/.well-known/openid-configuration"
    if marker in raw:
        return raw
    oidc_marker = "/protocol/openid-connect/"
    if oidc_marker in raw:
        return raw.split(oidc_marker, 1)[0].rstrip("/") + marker
    return ""


def oidc_discovery_candidates(connection: Dict[str, Any]) -> List[str]:
    """Prefer backchannel hosts (token/JWKS) over the browser-facing issuer."""
    seen: List[str] = []

    def add(url: str) -> None:
        cleaned = str(url or "").strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)

    for key in ("jwks_url", "token_url"):
        derived = _discovery_from_oidc_endpoint(str(connection.get(key) or ""))
        if derived:
            add(derived)
        elif key == "jwks_url" and connection.get(key):
            add(str(connection.get(key) or "").strip())
    issuer = str(connection.get("issuer") or "").rstrip("/")
    if issuer:
        add(f"{issuer}/.well-known/openid-configuration")
    return seen


def test_connection(alias: str) -> Tuple[Dict[str, Any], int]:
    payload, status = get_connection(alias)
    if status != 200:
        return payload, status
    connection = payload["connection"]
    protocol = connection.get("protocol")
    import httpx

    try:
        if protocol == "oidc":
            candidates = oidc_discovery_candidates(connection)
            if not candidates:
                if connection.get("authorization_url") and connection.get("token_url"):
                    return {"message": "OIDC endpoints are set. Discovery URL was not provided."}, 200
                return {"error": "OIDC issuer or authorization/token URLs are missing."}, 400
            last_error = None
            for url in candidates:
                try:
                    response = httpx.get(url, timeout=10.0)
                except httpx.HTTPError as exc:
                    last_error = exc
                    continue
                if response.status_code < 400:
                    return {"message": "OIDC discovery succeeded."}, 200
                last_error = response.status_code
            if isinstance(last_error, int):
                return {"error": f"OIDC discovery failed ({last_error})."}, 400
            logger.warning("SSO connection test failed for %s: %s", alias, last_error)
            return {"error": "Could not reach the identity provider."}, 400
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


def start_urls_for_protocol(protocol: str = "") -> List[Dict[str, str]]:
    wanted = str(protocol or "").strip().lower()
    payload, status = list_connections()
    if status != 200:
        return []
    rows = []
    for row in payload.get("connections") or []:
        if not row.get("enabled") or not row.get("alias") or not row.get("start_url"):
            continue
        if wanted and str(row.get("protocol") or "") != wanted:
            continue
        rows.append(
            {
                "alias": str(row["alias"]),
                "display_name": str(row.get("display_name") or row["alias"]),
                "url": str(row["start_url"]),
            }
        )
    if wanted and not rows:
        return start_urls_for_protocol("")
    return rows


def fetch_sp_metadata(alias: str) -> Tuple[Any, int, str]:
    payload, status = get_connection(alias)
    if status != 200:
        return payload, status, "application/json"
    connection = payload.get("connection") or {}
    if connection.get("protocol") != "saml":
        return {"error": "SP metadata is only available for SAML connections."}, 400, "application/json"
    cleaned = str(alias or "").strip()
    url = f"{keycloak_base_url()}/realms/{REALM}/broker/{cleaned}/endpoint/descriptor"
    import httpx

    try:
        response = httpx.get(url, timeout=10.0)
    except httpx.HTTPError as exc:
        logger.warning("Could not fetch SP metadata for %s: %s", alias, exc)
        return {"error": "Could not download SP metadata from Keycloak."}, 502, "application/json"
    if response.status_code >= 400 or not str(response.text or "").strip():
        return {"error": "Keycloak did not return SP metadata for this connection."}, 502, "application/json"
    return response.text, 200, "application/samlmetadata+xml"


__all__ = [
    "connection_public_view",
    "create_connection",
    "delete_connection",
    "fetch_sp_metadata",
    "get_connection",
    "list_connections",
    "list_login_providers",
    "oidc_discovery_candidates",
    "start_urls_for_protocol",
    "test_connection",
    "update_connection",
]
