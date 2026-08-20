import base64
import json
import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from app.integrations.keycloak.constants import (
    ACCESS_ROLE,
    BACKEND_CLIENT_ID,
    BACKEND_MANAGEMENT_ROLES,
    DIRECT_GRANT_FLOW,
    LDAP_COMPONENT_NAME,
    LOGIN_CLIENT_ID,
    MASTER_REALM,
    REALM,
    SERVICE_SCOPE_ROLES,
    backend_client_secret,
    keycloak_base_url,
    login_client_secret,
    master_admin_password,
    master_admin_username,
)

logger = logging.getLogger(__name__)


class KeycloakAdminError(RuntimeError):
    def __init__(self, message: str, status_code: int = 0, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def decode_access_token(token: str) -> Dict[str, Any]:
    parts = str(token or "").split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padded = payload + "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _realm_roles_from_claims(claims: Dict[str, Any]) -> List[str]:
    realm_access = claims.get("realm_access") or {}
    roles = realm_access.get("roles") or []
    if not isinstance(roles, list):
        return []
    return [str(item) for item in roles if item]


def _client_roles_from_claims(claims: Dict[str, Any], client_id: str) -> List[str]:
    resource_access = claims.get("resource_access") or {}
    if not isinstance(resource_access, dict):
        return []
    entry = resource_access.get(client_id) or {}
    roles = entry.get("roles") or []
    if not isinstance(roles, list):
        return []
    return [str(item) for item in roles if item]


def password_grant(username: str, password: str, timeout: float = 15.0) -> Dict[str, Any]:
    """Resource-owner password grant against raptor-login. Does not raise on 4xx."""
    token_url = f"{keycloak_base_url()}/realms/{REALM}/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": LOGIN_CLIENT_ID,
        "client_secret": login_client_secret(),
        "username": username,
        "password": password,
    }
    try:
        response = httpx.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        logger.error("Keycloak password grant failed: %s", exc)
        return {"status": "error", "error": "identity provider unavailable"}

    if response.status_code == 200:
        payload = response.json()
        token = str(payload.get("access_token") or "")
        claims = decode_access_token(token)
        return {
            "status": "ok",
            "access_token": token,
            "claims": claims,
            "realm_roles": _realm_roles_from_claims(claims),
            "client_roles": _client_roles_from_claims(claims, LOGIN_CLIENT_ID),
        }

    body: Dict[str, Any] = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            body = parsed
    except ValueError:
        body = {}
    description = str(body.get("error_description") or body.get("error") or "")
    lowered = description.lower()
    if response.status_code in {400, 401} and "not fully set up" in lowered:
        return {"status": "reset_required", "error": description}
    if response.status_code in {400, 401}:
        return {"status": "invalid", "error": description or "Invalid credentials"}
    logger.error("Keycloak password grant unexpected status %s: %s", response.status_code, description)
    return {"status": "error", "error": description or "identity provider error"}


def client_credentials_grant(
    client_id: str,
    client_secret: str,
    timeout: float = 15.0,
) -> Tuple[Optional[Dict[str, Any]], int]:
    token_url = f"{keycloak_base_url()}/realms/{REALM}/protocol/openid-connect/token"
    try:
        response = httpx.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        logger.error("Keycloak client-credentials grant failed: %s", exc)
        return None, 503
    if response.status_code != 200:
        return None, response.status_code
    payload = response.json()
    token = str(payload.get("access_token") or "")
    claims = decode_access_token(token)
    return {
        "access_token": token,
        "claims": claims,
        "client_roles": _client_roles_from_claims(claims, client_id),
        "realm_roles": _realm_roles_from_claims(claims),
    }, 200


class KeycloakClient:
    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires_at = 0.0
        self._using_master = False

    def wait_ready(self, attempts: int = 60, delay_seconds: float = 2.0) -> None:
        last_error = None
        for _ in range(max(1, attempts)):
            try:
                response = httpx.get(
                    f"{keycloak_base_url()}/realms/master",
                    timeout=5.0,
                )
                if response.status_code < 500:
                    return
                last_error = f"status {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(delay_seconds)
        raise KeycloakAdminError(f"Keycloak did not become ready: {last_error}")

    def _fetch_token(self, realm: str, client_id: str, extra: Dict[str, str]) -> Optional[str]:
        token_url = f"{keycloak_base_url()}/realms/{realm}/protocol/openid-connect/token"
        data = {"client_id": client_id, **extra}
        try:
            response = httpx.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            logger.warning("Keycloak token request failed: %s", exc)
            return None
        if response.status_code != 200:
            logger.debug("Keycloak token request %s: %s", response.status_code, response.text[:300])
            return None
        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        expires_in = int(payload.get("expires_in") or 60)
        if token:
            self._token = token
            self._token_expires_at = time.time() + max(30, expires_in - 15)
        return token or None

    def _ensure_token(self, force: bool = False) -> str:
        if not force and self._token and time.time() < self._token_expires_at:
            return self._token
        backend_secret = backend_client_secret()
        if backend_secret:
            token = self._fetch_token(
                REALM,
                BACKEND_CLIENT_ID,
                {"grant_type": "client_credentials", "client_secret": backend_secret},
            )
            if token:
                self._using_master = False
                return token
        password = master_admin_password()
        if password:
            token = self._fetch_token(
                MASTER_REALM,
                "admin-cli",
                {
                    "grant_type": "password",
                    "username": master_admin_username(),
                    "password": password,
                },
            )
            if token:
                self._using_master = True
                return token
        raise KeycloakAdminError("Unable to obtain a Keycloak admin token")

    def request(
        self,
        method: str,
        path: str,
        *,
        realm: Optional[str] = None,
        expected: Iterable[int] = (200, 201, 204),
        **kwargs,
    ) -> httpx.Response:
        target_realm = realm or REALM
        url = f"{keycloak_base_url()}/admin/realms/{target_realm}{path}"
        expected_set = set(expected)
        last_error: Optional[Exception] = None
        for attempt in range(2):
            token = self._ensure_token(force=attempt == 1)
            headers = dict(kwargs.pop("headers", {}) or {})
            headers["Authorization"] = f"Bearer {token}"
            try:
                response = httpx.request(
                    method,
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    **kwargs,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                continue
            if response.status_code == 401 and attempt == 0:
                continue
            if response.status_code not in expected_set:
                raise KeycloakAdminError(
                    f"{method} {path} failed ({response.status_code}): {response.text[:400]}",
                    status_code=response.status_code,
                    body=response.text,
                )
            return response
        raise KeycloakAdminError(f"{method} {path} failed: {last_error}")

    def json(self, method: str, path: str, **kwargs) -> Any:
        response = self.request(method, path, **kwargs)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def ensure_schema_placeholder(self) -> None:
        """No-op kept for call-site symmetry with bootstrap."""
        return None

    def get_realm(self) -> Optional[Dict[str, Any]]:
        try:
            payload = self.json("GET", "", expected=(200,))
        except KeycloakAdminError as exc:
            if exc.status_code == 404:
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def create_realm(self, representation: Dict[str, Any]) -> None:
        # Realm create is on /admin/realms, not /admin/realms/{realm}
        url = f"{keycloak_base_url()}/admin/realms"
        token = self._ensure_token()
        response = httpx.post(
            url,
            json=representation,
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if response.status_code not in {201, 204, 409}:
            raise KeycloakAdminError(
                f"Failed to create realm: {response.status_code} {response.text[:400]}",
                status_code=response.status_code,
                body=response.text,
            )

    def update_realm(self, representation: Dict[str, Any]) -> None:
        self.request("PUT", "", json=representation, expected=(204,))

    def get_client_by_client_id(self, client_id: str) -> Optional[Dict[str, Any]]:
        rows = self.json("GET", f"/clients?{urlencode({'clientId': client_id, 'max': 2})}") or []
        if not isinstance(rows, list):
            return None
        for row in rows:
            if isinstance(row, dict) and row.get("clientId") == client_id:
                return row
        return None

    def ensure_client(self, representation: Dict[str, Any]) -> Dict[str, Any]:
        client_id = str(representation.get("clientId") or "")
        existing = self.get_client_by_client_id(client_id)
        secret = representation.get("secret")
        if existing:
            client_uuid = existing["id"]
            merged = dict(existing)
            for key, value in representation.items():
                if key == "id":
                    continue
                merged[key] = value
            merged["id"] = client_uuid
            self.request("PUT", f"/clients/{client_uuid}", json=merged, expected=(204,))
            if secret:
                self.set_client_secret(client_uuid, secret)
            return self.get_client_by_client_id(client_id) or merged
        self.request("POST", "/clients", json=representation, expected=(201, 409))
        created = self.get_client_by_client_id(client_id)
        if not created:
            raise KeycloakAdminError(f"Client {client_id} was not created")
        if secret:
            self.set_client_secret(created["id"], secret)
        return created

    def set_client_secret(self, client_uuid: str, secret: str) -> None:
        self.request(
            "POST",
            f"/clients/{client_uuid}/client-secret",
            json={"type": "secret", "value": secret},
            expected=(200, 204),
        )
        # Some Keycloak versions ignore POST value; PUT the client secret field too.
        current = self.json("GET", f"/clients/{client_uuid}") or {}
        if isinstance(current, dict):
            current["secret"] = secret
            self.request("PUT", f"/clients/{client_uuid}", json=current, expected=(204,))

    def delete_client(self, client_uuid: str) -> None:
        self.request("DELETE", f"/clients/{client_uuid}", expected=(204, 404))

    def get_realm_role(self, name: str) -> Optional[Dict[str, Any]]:
        try:
            payload = self.json("GET", f"/roles/{name}", expected=(200,))
        except KeycloakAdminError as exc:
            if exc.status_code == 404:
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def ensure_realm_role(self, name: str, description: str = "", composite: bool = False) -> Dict[str, Any]:
        existing = self.get_realm_role(name)
        body = {"name": name, "description": description, "composite": composite}
        if existing:
            body["id"] = existing.get("id")
            self.request("PUT", f"/roles/{name}", json={**existing, **body}, expected=(204,))
            return self.get_realm_role(name) or existing
        self.request("POST", "/roles", json=body, expected=(201, 409))
        created = self.get_realm_role(name)
        if not created:
            raise KeycloakAdminError(f"Realm role {name} was not created")
        return created

    def get_client_role(self, client_uuid: str, name: str) -> Optional[Dict[str, Any]]:
        try:
            payload = self.json("GET", f"/clients/{client_uuid}/roles/{name}", expected=(200,))
        except KeycloakAdminError as exc:
            if exc.status_code == 404:
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def ensure_client_role(self, client_uuid: str, name: str, description: str = "") -> Dict[str, Any]:
        existing = self.get_client_role(client_uuid, name)
        if existing:
            return existing
        self.request(
            "POST",
            f"/clients/{client_uuid}/roles",
            json={"name": name, "description": description},
            expected=(201, 409),
        )
        created = self.get_client_role(client_uuid, name)
        if not created:
            raise KeycloakAdminError(f"Client role {name} was not created")
        return created

    def set_realm_role_composites(
        self,
        role_name: str,
        realm_roles: List[Dict[str, Any]],
        client_roles_by_uuid: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        existing = self.json("GET", f"/roles/{role_name}/composites", expected=(200, 404)) or []
        if existing:
            self.request(
                "DELETE",
                f"/roles/{role_name}/composites",
                json=existing,
                expected=(204,),
            )
        to_add = list(realm_roles)
        for roles in client_roles_by_uuid.values():
            to_add.extend(roles)
        if to_add:
            self.request("POST", f"/roles/{role_name}/composites", json=to_add, expected=(204,))

    def find_user(self, username: str) -> Optional[Dict[str, Any]]:
        rows = self.json(
            "GET",
            f"/users?{urlencode({'username': username, 'exact': 'true', 'max': 5})}",
        ) or []
        if not isinstance(rows, list):
            return None
        lowered = username.strip().lower()
        for row in rows:
            if isinstance(row, dict) and str(row.get("username") or "").strip().lower() == lowered:
                return row
        return rows[0] if rows and isinstance(rows[0], dict) else None

    def search_users(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        rows = self.json(
            "GET",
            f"/users?{urlencode({'search': query, 'max': max_results})}",
        ) or []
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            payload = self.json("GET", f"/users/{user_id}", expected=(200,))
        except KeycloakAdminError as exc:
            if exc.status_code == 404:
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def create_user(self, representation: Dict[str, Any]) -> str:
        response = self.request("POST", "/users", json=representation, expected=(201, 409))
        location = response.headers.get("Location") or ""
        if location.rsplit("/", 1)[-1]:
            user_id = location.rsplit("/", 1)[-1]
            if user_id:
                return user_id
        created = self.find_user(str(representation.get("username") or ""))
        if not created:
            raise KeycloakAdminError("User create did not return an id")
        return str(created["id"])

    def update_user(self, user_id: str, representation: Dict[str, Any]) -> None:
        current = self.get_user(user_id) or {}
        merged = {**current, **representation, "id": user_id}
        self.request("PUT", f"/users/{user_id}", json=merged, expected=(204,))

    def delete_user(self, user_id: str) -> None:
        self.request("DELETE", f"/users/{user_id}", expected=(204, 404))

    def set_password(self, user_id: str, password: str, temporary: bool = False) -> None:
        self.request(
            "PUT",
            f"/users/{user_id}/reset-password",
            json={"type": "password", "value": password, "temporary": temporary},
            expected=(204,),
        )

    def clear_brute_force(self, user_id: str) -> None:
        self.request(
            "DELETE",
            f"/attack-detection/brute-force/users/{user_id}",
            expected=(204, 200, 404),
        )

    def get_user_realm_roles(self, user_id: str) -> List[Dict[str, Any]]:
        rows = self.json("GET", f"/users/{user_id}/role-mappings/realm") or []
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def replace_user_raptor_realm_roles(self, user_id: str, roles: List[Dict[str, Any]]) -> None:
        current = self.get_user_realm_roles(user_id)
        raptor_current = [row for row in current if str(row.get("name") or "").startswith("raptor-")]
        if raptor_current:
            self.request(
                "DELETE",
                f"/users/{user_id}/role-mappings/realm",
                json=raptor_current,
                expected=(204,),
            )
        if roles:
            self.request("POST", f"/users/{user_id}/role-mappings/realm", json=roles, expected=(204,))

    def get_user_client_roles(self, user_id: str, client_uuid: str) -> List[Dict[str, Any]]:
        rows = self.json("GET", f"/users/{user_id}/role-mappings/clients/{client_uuid}") or []
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def replace_user_client_roles(
        self, user_id: str, client_uuid: str, roles: List[Dict[str, Any]]
    ) -> None:
        current = self.get_user_client_roles(user_id, client_uuid)
        if current:
            self.request(
                "DELETE",
                f"/users/{user_id}/role-mappings/clients/{client_uuid}",
                json=current,
                expected=(204,),
            )
        if roles:
            self.request(
                "POST",
                f"/users/{user_id}/role-mappings/clients/{client_uuid}",
                json=roles,
                expected=(204,),
            )

    def list_components(self, provider_type: str) -> List[Dict[str, Any]]:
        rows = self.json("GET", f"/components?{urlencode({'type': provider_type})}") or []
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def ensure_ldap_federation(self, config: Dict[str, List[str]], realm_id: str) -> Optional[str]:
        provider_type = "org.keycloak.storage.UserStorageProvider"
        existing = [
            row
            for row in self.list_components(provider_type)
            if row.get("name") == LDAP_COMPONENT_NAME
        ]
        body = {
            "name": LDAP_COMPONENT_NAME,
            "providerId": "ldap",
            "providerType": provider_type,
            "parentId": realm_id,
            "config": config,
        }
        if existing:
            current = existing[0]
            current_id = str(current["id"])
            merged = {**current, **body, "id": current_id}
            self.request("PUT", f"/components/{current_id}", json=merged, expected=(204,))
            return current_id
        response = self.request("POST", "/components", json=body, expected=(201, 409))
        location = response.headers.get("Location") or ""
        created_id = location.rsplit("/", 1)[-1] if location else ""
        if created_id:
            return created_id
        created = [
            row
            for row in self.list_components(provider_type)
            if row.get("name") == LDAP_COMPONENT_NAME
        ]
        return str(created[0]["id"]) if created else None

    def set_ldap_federation_enabled(self, enabled: bool) -> bool:
        provider_type = "org.keycloak.storage.UserStorageProvider"
        existing = [
            row
            for row in self.list_components(provider_type)
            if row.get("name") == LDAP_COMPONENT_NAME
        ]
        if not existing:
            return False
        current = existing[0]
        current_id = str(current["id"])
        config = dict(current.get("config") or {})
        config["enabled"] = ["true" if enabled else "false"]
        current["config"] = config
        self.request("PUT", f"/components/{current_id}", json=current, expected=(204,))
        return True

    def test_ldap_connection(
        self,
        action: str,
        connection_url: str,
        bind_dn: str,
        bind_credential: str,
        *,
        use_truststore: str = "never",
        start_tls: str = "false",
        auth_type: str = "simple",
        connection_timeout: str = "10000",
    ) -> None:
        self.request(
            "POST",
            "/testLDAPConnection",
            json={
                "action": action,
                "connectionUrl": connection_url,
                "bindDn": bind_dn,
                "bindCredential": bind_credential,
                "useTruststoreSpi": use_truststore,
                "connectionTimeout": connection_timeout,
                "startTls": start_tls,
                "authType": auth_type,
            },
            expected=(204, 200),
        )

    def list_identity_providers(self) -> List[Dict[str, Any]]:
        rows = self.json("GET", "/identity-provider/instances") or []
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def get_identity_provider(self, alias: str) -> Optional[Dict[str, Any]]:
        try:
            payload = self.json("GET", f"/identity-provider/instances/{alias}", expected=(200,))
        except KeycloakAdminError as exc:
            if exc.status_code == 404:
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def ensure_identity_provider(self, representation: Dict[str, Any]) -> Dict[str, Any]:
        alias = str(representation.get("alias") or "").strip()
        if not alias:
            raise KeycloakAdminError("Identity provider alias is required")
        existing = self.get_identity_provider(alias)
        if existing:
            merged = dict(existing)
            for key, value in representation.items():
                if key == "config":
                    current_config = dict(existing.get("config") or {})
                    incoming = dict(value or {})
                    secret = str(incoming.get("clientSecret") or "").strip()
                    if not secret:
                        incoming.pop("clientSecret", None)
                    current_config.update(incoming)
                    merged["config"] = current_config
                    continue
                merged[key] = value
            self.request("PUT", f"/identity-provider/instances/{alias}", json=merged, expected=(204,))
            return self.get_identity_provider(alias) or merged
        self.request("POST", "/identity-provider/instances", json=representation, expected=(201, 409))
        created = self.get_identity_provider(alias)
        if not created:
            raise KeycloakAdminError(f"Identity provider {alias} was not created")
        return created

    def get_federated_identities(self, user_id: str) -> List[Dict[str, Any]]:
        rows = self.json("GET", f"/users/{user_id}/federated-identity") or []
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def relax_user_profile_required_attributes(self) -> None:
        """Stop Keycloak VERIFY_PROFILE from blocking LDAP/IdP users with empty names."""
        try:
            profile = self.json("GET", "/users/profile", expected=(200,))
        except KeycloakAdminError as exc:
            logger.info("Could not load Keycloak user profile: %s", exc)
            return
        if not isinstance(profile, dict):
            return
        changed = False
        for attr in profile.get("attributes") or []:
            if not isinstance(attr, dict):
                continue
            if attr.get("name") not in {"firstName", "lastName", "email"}:
                continue
            required = attr.get("required")
            if required:
                attr["required"] = {}
                changed = True
        if not changed:
            return
        try:
            self.request("PUT", "/users/profile", json=profile, expected=(200, 204))
        except KeycloakAdminError as exc:
            logger.warning("Could not relax Keycloak user-profile required attributes: %s", exc)

    def ensure_direct_grant_allowlist_flow(self) -> None:
        """Copy Direct Grant and deny users missing raptor-access. Best-effort."""
        flows = self.json("GET", "/authentication/flows") or []
        if not isinstance(flows, list):
            return
        aliases = {str(flow.get("alias") or "") for flow in flows if isinstance(flow, dict)}
        if DIRECT_GRANT_FLOW not in aliases:
            try:
                self.request(
                    "POST",
                    "/authentication/flows/direct grant/copy",
                    json={"newName": DIRECT_GRANT_FLOW},
                    expected=(201, 204, 409),
                )
            except KeycloakAdminError as exc:
                logger.warning("Could not copy direct grant flow: %s", exc)
                return
        try:
            self.request(
                "POST",
                f"/authentication/flows/{DIRECT_GRANT_FLOW}/executions/flow",
                json={
                    "alias": "raptor-access-gate",
                    "description": "Deny login unless raptor-access is assigned",
                    "provider": "basic-flow",
                    "type": "basic-flow",
                },
                expected=(201, 204, 409),
            )
        except KeycloakAdminError as exc:
            if exc.status_code not in {409}:
                logger.info("Direct-grant gate subflow: %s", exc)

        executions = self.json("GET", f"/authentication/flows/{DIRECT_GRANT_FLOW}/executions") or []
        gate = None
        if isinstance(executions, list):
            for row in executions:
                if isinstance(row, dict) and row.get("displayName") in {
                    "raptor-access-gate",
                    "Raptor-access-gate",
                }:
                    gate = row
                    break
                if isinstance(row, dict) and row.get("alias") == "raptor-access-gate":
                    gate = row
                    break
        if not gate:
            logger.warning("raptor-access-gate subflow not found; Flask will still enforce raptor-access")
        else:
            flow_id = gate.get("id") or gate.get("flowId")
            if flow_id:
                self.request(
                    "PUT",
                    "/authentication/flows/raptor-access-gate/executions",
                    json={
                        "id": flow_id,
                        "requirement": "REQUIRED",
                    },
                    expected=(202, 204, 400),
                )
            try:
                self.request(
                    "POST",
                    "/authentication/flows/raptor-access-gate/executions/execution",
                    json={"provider": "conditional-user-role"},
                    expected=(201, 204, 409),
                )
                self.request(
                    "POST",
                    "/authentication/flows/raptor-access-gate/executions/execution",
                    json={"provider": "deny-access-authenticator"},
                    expected=(201, 204, 409),
                )
                nested = self.json("GET", "/authentication/flows/raptor-access-gate/executions") or []
                if isinstance(nested, list):
                    for row in nested:
                        if not isinstance(row, dict):
                            continue
                        provider = str(row.get("providerId") or row.get("provider") or "")
                        if provider == "conditional-user-role":
                            config_id = row.get("id")
                            if config_id:
                                self.request(
                                    "PUT",
                                    f"/authentication/config",
                                    json={
                                        "alias": "require-raptor-access",
                                        "config": {
                                            "condUserRole": ACCESS_ROLE,
                                            "negate": "true",
                                        },
                                    },
                                    expected=(201, 204, 400),
                                )
                                self.request(
                                    "POST",
                                    f"/authentication/executions/{config_id}/config",
                                    json={
                                        "alias": "require-raptor-access",
                                        "config": {
                                            "condUserRole": ACCESS_ROLE,
                                            "negate": "true",
                                        },
                                    },
                                    expected=(201, 204, 409),
                                )
            except KeycloakAdminError as exc:
                logger.warning("Could not finish raptor-access direct-grant gate: %s", exc)

        # Incomplete custom copies 500 the token endpoint. Flask already checks raptor-access.
        realm = self.get_realm() or {}
        if realm.get("directGrantFlow") != "direct grant":
            realm["directGrantFlow"] = "direct grant"
            try:
                self.update_realm(realm)
            except KeycloakAdminError as exc:
                logger.warning("Could not restore built-in direct grant flow: %s", exc)

    def ensure_service_scope_roles(self, client_uuid: str) -> Dict[str, Dict[str, Any]]:
        mapping = {}
        for name in SERVICE_SCOPE_ROLES:
            mapping[name] = self.ensure_client_role(client_uuid, name, description=f"RAPTOR API scope {name}")
        return mapping

    def ensure_backend_service_account_privileges(self) -> None:
        management = self.get_client_by_client_id("realm-management")
        if not management:
            logger.warning("realm-management client is missing; backend Admin API calls may fail")
            return
        management_uuid = str(management["id"])
        service_user = self.find_user(f"service-account-{BACKEND_CLIENT_ID}")
        if not service_user:
            logger.warning("Keycloak backend service-account user is missing")
            return
        current = self.get_user_client_roles(str(service_user["id"]), management_uuid)
        have = {str(row.get("name") or "") for row in current}
        to_add = []
        for name in BACKEND_MANAGEMENT_ROLES:
            if name in have:
                continue
            role = self.get_client_role(management_uuid, name)
            if role:
                to_add.append(role)
        if not to_add:
            return
        self.request(
            "POST",
            f"/users/{service_user['id']}/role-mappings/clients/{management_uuid}",
            json=to_add,
            expected=(204,),
        )


def admin_client() -> KeycloakClient:
    return KeycloakClient()


__all__ = [
    "KeycloakAdminError",
    "KeycloakClient",
    "admin_client",
    "client_credentials_grant",
    "decode_access_token",
    "password_grant",
]
