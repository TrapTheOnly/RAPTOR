from app.integrations.keycloak.constants import (
    is_supported_sso_provider,
    keycloak_public_url,
    login_redirect_uris,
    raptor_public_url,
    realm_issuer_url,
    sso_callback_url,
    sso_protocol,
    sso_start_url,
)
from app.services import keycloak_bootstrap_service as bootstrap
from app.services import sso_settings_service as sso_settings
from app.services import sso_auth_service as sso_auth


def test_keycloak_public_url_defaults_when_internal(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
    monkeypatch.delenv("KEYCLOAK_PUBLIC_URL", raising=False)
    assert keycloak_public_url() == "http://localhost:8180"


def test_keycloak_public_url_explicit(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_PUBLIC_URL", "https://auth.example.com/")
    assert keycloak_public_url() == "https://auth.example.com"


def test_raptor_public_url_and_callback(monkeypatch):
    monkeypatch.setenv("RAPTOR_PUBLIC_URL", "https://raptor.example.com")
    assert raptor_public_url() == "https://raptor.example.com"
    assert sso_callback_url() == "https://raptor.example.com/auth/sso/callback"
    assert "https://raptor.example.com/auth/sso/callback" in login_redirect_uris()
    assert sso_start_url("corp-okta") == "https://raptor.example.com/auth/sso/corp-okta/start"
    assert "/realms/" in realm_issuer_url()


def test_oidc_discovery_candidates_prefers_backchannel():
    urls = sso_settings.oidc_discovery_candidates(
        {
            "issuer": "http://localhost:8280/realms/corp",
            "authorization_url": "http://localhost:8280/realms/corp/protocol/openid-connect/auth",
            "token_url": "http://corp-idp:8080/realms/corp/protocol/openid-connect/token",
            "jwks_url": "http://corp-idp:8080/realms/corp/protocol/openid-connect/certs",
        }
    )
    assert urls[0] == "http://corp-idp:8080/realms/corp/.well-known/openid-configuration"
    assert urls[-1] == "http://localhost:8280/realms/corp/.well-known/openid-configuration"
    assert urls.count("http://corp-idp:8080/realms/corp/.well-known/openid-configuration") == 1


def test_oidc_connection_test_uses_backchannel_when_issuer_is_local(monkeypatch):
    import httpx

    class FakeResponse:
        status_code = 200

    seen = []

    def fake_get(url, timeout=10.0):
        seen.append(url)
        if "corp-idp" in url:
            return FakeResponse()
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(
        sso_settings,
        "get_connection",
        lambda alias: (
            {
                "connection": {
                    "protocol": "oidc",
                    "issuer": "http://localhost:8280/realms/corp",
                    "token_url": "http://corp-idp:8080/realms/corp/protocol/openid-connect/token",
                    "jwks_url": "http://corp-idp:8080/realms/corp/protocol/openid-connect/certs",
                }
            },
            200,
        ),
    )
    monkeypatch.setattr(httpx, "get", fake_get)
    payload, status = sso_settings.test_connection("test-oidc")
    assert status == 200
    assert payload["message"] == "OIDC discovery succeeded."
    assert seen[0].startswith("http://corp-idp:8080/")


def test_sso_protocol_allowlist():
    assert sso_protocol("keycloak-oidc") == "oidc"
    assert sso_protocol("saml") == "saml"
    assert is_supported_sso_provider("oidc")
    assert is_supported_sso_provider("saml")
    assert not is_supported_sso_provider("google")
    assert not is_supported_sso_provider("github")


def test_connection_public_view_strips_secret(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_PUBLIC_URL", "http://localhost:8180")
    monkeypatch.setenv("RAPTOR_PUBLIC_URL", "http://localhost:1337")
    view = sso_settings.connection_public_view(
        {
            "alias": "corp-oidc",
            "displayName": "Corp",
            "providerId": "oidc",
            "enabled": True,
            "config": {"clientId": "raptor", "clientSecret": "super-secret", "issuer": "https://idp"},
        }
    )
    assert view["has_client_secret"] is True
    assert "clientSecret" not in view
    assert view["protocol"] == "oidc"
    assert view["redirect_uri"].endswith("/auth/sso/callback")
    assert view["acs_url"] == "http://localhost:8180/realms/raptor/broker/corp-oidc/endpoint"
    assert view["broker_redirect_uri"] == view["acs_url"]
    assert view["sp_entity_id"] == "http://localhost:8180/realms/raptor"
    assert view["start_url"] == "http://localhost:1337/auth/sso/corp-oidc/start"
    assert view["sp_metadata_url"] == ""


def test_connection_public_view_saml_operator_urls(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_PUBLIC_URL", "https://auth.example.com")
    monkeypatch.setenv("RAPTOR_PUBLIC_URL", "https://raptor.example.com")
    view = sso_settings.connection_public_view(
        {
            "alias": "corp-saml",
            "displayName": "Corp SAML",
            "providerId": "saml",
            "enabled": True,
            "config": {"idpEntityId": "http://idp.example.com", "singleSignOnServiceUrl": "https://idp/sso"},
        }
    )
    assert view["acs_url"] == "https://auth.example.com/realms/raptor/broker/corp-saml/endpoint"
    assert view["sp_entity_id"] == "https://auth.example.com/realms/raptor"
    assert view["sp_entity_id"] != view["entity_id"]
    assert view["start_url"].endswith("/auth/sso/corp-saml/start")
    assert view["sp_metadata_url"].endswith("/broker/corp-saml/endpoint/descriptor")


def test_connection_public_view_ignores_placeholder_secret():
    view = sso_settings.connection_public_view(
        {
            "alias": "corp",
            "providerId": "oidc",
            "config": {"clientSecret": "**********"},
        }
    )
    assert view["has_client_secret"] is False


_SAML_METADATA = """<?xml version="1.0"?>
<EntityDescriptor entityID="http://localhost:8280/realms/corp"
    xmlns="urn:oasis:names:tc:SAML:2.0:metadata">
  <IDPSSODescriptor WantAuthnRequestsSigned="true"
      protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <SingleLogoutService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        Location="http://localhost:8280/realms/corp/protocol/saml"/>
    <SingleSignOnService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        Location="http://localhost:8280/realms/corp/protocol/saml"/>
    <SingleSignOnService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        Location="http://localhost:8280/realms/corp/protocol/saml"/>
  </IDPSSODescriptor>
</EntityDescriptor>
"""


def test_parse_saml_idp_metadata_prefers_http_post():
    parsed = sso_settings.parse_saml_idp_metadata(_SAML_METADATA)
    assert parsed["entity_id"] == "http://localhost:8280/realms/corp"
    assert parsed["sso_url"] == "http://localhost:8280/realms/corp/protocol/saml"
    assert parsed["logout_url"] == "http://localhost:8280/realms/corp/protocol/saml"
    assert parsed["want_authn_requests_signed"] == "true"


def test_parse_saml_idp_metadata_empty_or_invalid():
    assert sso_settings.parse_saml_idp_metadata("") == {}
    assert sso_settings.parse_saml_idp_metadata("<not-xml") == {}


def test_saml_accepts_metadata_url_without_manual_idp_fields(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = _SAML_METADATA

    monkeypatch.setattr("httpx.get", lambda url, timeout=10.0: FakeResponse())
    payload, error = sso_settings._representation_from_payload(
        {
            "alias": "corp-saml",
            "protocol": "saml",
            "display_name": "Corp",
            "metadata_url": "https://idp.example.com/metadata",
        }
    )
    assert error is None
    assert payload["config"]["metadataDescriptorUrl"] == "https://idp.example.com/metadata"
    assert payload["config"]["useMetadataDescriptorUrl"] == "true"
    assert payload["config"]["idpEntityId"] == "http://localhost:8280/realms/corp"
    assert payload["config"]["entityId"] != payload["config"]["idpEntityId"]
    assert payload["config"]["singleSignOnServiceUrl"] == "http://localhost:8280/realms/corp/protocol/saml"
    assert payload["config"]["wantAuthnRequestsSigned"] == "true"


def test_saml_metadata_only_still_valid_when_fetch_fails(monkeypatch):
    import httpx

    def boom(url, timeout=10.0):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr("httpx.get", boom)
    payload, error = sso_settings._representation_from_payload(
        {
            "alias": "corp-saml",
            "protocol": "saml",
            "display_name": "Corp",
            "metadata_url": "https://idp.example.com/metadata",
        }
    )
    assert error is None
    assert payload["config"]["metadataDescriptorUrl"] == "https://idp.example.com/metadata"
    assert "singleSignOnServiceUrl" not in payload["config"]


def test_google_oidc_maps_principal_to_email():
    payload, error = sso_settings._representation_from_payload(
        {
            "alias": "google-oidc",
            "protocol": "oidc",
            "display_name": "Google",
            "client_id": "raptor.apps.googleusercontent.com",
            "client_secret": "secret",
            "issuer": "https://accounts.google.com",
        }
    )
    assert error is None
    assert payload["config"]["principalType"] == "ATTRIBUTE"
    assert payload["config"]["principalAttribute"] == "email"


def test_saml_requires_idp_fields_without_metadata():
    payload, error = sso_settings._representation_from_payload(
        {"alias": "corp-saml", "protocol": "saml", "display_name": "Corp"}
    )
    assert payload is None
    assert "metadata" in error.lower()


def test_ensure_idp_skips_existing(monkeypatch):
    calls = []

    class FakeClient:
        def ensure_raptor_first_broker_flow(self):
            return "raptor first broker"

        def get_identity_provider(self, alias):
            return {"alias": alias, "providerId": "oidc"}

        def ensure_identity_provider(self, representation):
            calls.append(representation)
            return representation

    monkeypatch.setenv("KEYCLOAK_IDP_ALIAS", "corp-oidc")
    monkeypatch.setenv("KEYCLOAK_IDP_PROVIDER", "oidc")
    monkeypatch.setenv("KEYCLOAK_IDP_CLIENT_ID", "raptor")
    monkeypatch.setenv("KEYCLOAK_IDP_ISSUER", "https://idp.example.com")
    bootstrap._ensure_identity_provider(FakeClient())
    assert calls == []


def test_login_client_enables_standard_flow(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_LOGIN_CLIENT_SECRET", "secret")
    monkeypatch.setenv("RAPTOR_PUBLIC_URL", "http://localhost:1337")
    payload = bootstrap._login_client_representation()
    assert payload["standardFlowEnabled"] is True
    assert payload["directAccessGrantsEnabled"] is True
    assert payload["baseUrl"] == "http://localhost:1337/login"
    assert payload["rootUrl"] == "http://localhost:1337"
    assert any(item.endswith("/auth/sso/callback") for item in payload["redirectUris"])


def test_create_connection_rejects_google():
    payload, status = sso_settings._representation_from_payload({"alias": "google", "protocol": "google"})
    assert payload is None
    assert status == "Protocol must be oidc or saml."


def test_sso_start_rejects_unsupported_provider(monkeypatch):
    class FakeClient:
        def get_identity_provider(self, alias):
            return {"alias": alias, "providerId": "google", "enabled": True}

    monkeypatch.setattr("app.integrations.keycloak.client.KeycloakClient", lambda: FakeClient())
    url, error = sso_auth.authorization_url("google", {})
    assert url is None
    assert error == "unsupported"


def test_sso_callback_invalid_state():
    session = {"sso_state": "abc", "sso_code_verifier": "ver"}
    target, error = sso_auth.complete_sso_callback(session, {"state": "nope", "code": "x"})
    assert target == "/login"
    assert error == "invalid_state"


def test_identity_session_valid_without_tokens():
    assert sso_auth.identity_session_valid({"logged_in": True}) is False
    assert sso_auth.drop_invalid_identity_session({}) is False
    dropped = {"logged_in": True}
    assert sso_auth.drop_invalid_identity_session(dropped) is True
    assert dropped == {}


def test_identity_session_valid_db_error_is_invalid(monkeypatch):
    monkeypatch.setattr(
        sso_auth,
        "get_session_tokens",
        lambda session_key: (_ for _ in ()).throw(RuntimeError("db down")),
    )
    assert sso_auth.identity_session_valid({"logged_in": True, "kc_session_key": "abc"}) is False


def test_id_token_claims_require_nonce(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_PUBLIC_URL", "http://localhost:8180")
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
    claims = {
        "nonce": "abc",
        "iss": "http://localhost:8180/realms/raptor",
        "aud": "raptor-login",
        "exp": 9999999999,
    }
    assert sso_auth._id_token_claims_valid(claims, "abc") is True
    assert sso_auth._id_token_claims_valid(claims, "nope") is False
    assert sso_auth._id_token_claims_valid({**claims, "aud": "other"}, "abc") is False


def test_sso_callback_rejects_missing_nonce(monkeypatch):
    monkeypatch.setattr(
        sso_auth,
        "authorization_code_grant",
        lambda code, redirect_uri, verifier: {
            "status": "ok",
            "id_token": "header.payload.sig",
            "claims": {"preferred_username": "alice", "sub": "kc-1"},
            "id_claims": {"preferred_username": "alice", "sub": "kc-1"},
            "realm_roles": ["raptor-access"],
        },
    )
    monkeypatch.setattr(sso_auth, "verify_oidc_id_token", lambda token, nonce: False)
    session = {
        "sso_state": "abc",
        "sso_nonce": "nonce-1",
        "sso_code_verifier": "ver",
        "sso_alias": "corp",
        "sso_redirect_uri": "http://localhost:1337/auth/sso/callback",
    }
    target, error = sso_auth.complete_sso_callback(session, {"state": "abc", "code": "x"})
    assert target == "/login"
    assert error == "invalid_state"


def test_sso_callback_revokes_unallowlisted_user(monkeypatch):
    revoked = []
    monkeypatch.setattr(
        sso_auth,
        "authorization_code_grant",
        lambda code, redirect_uri, verifier: {
            "status": "ok",
            "id_token": "header.payload.sig",
            "claims": {"preferred_username": "mallory", "email": "alice@corp.com", "sub": "kc-evil"},
            "id_claims": {"preferred_username": "mallory", "email": "alice@corp.com", "sub": "kc-evil"},
            "realm_roles": [],
        },
    )
    monkeypatch.setattr(sso_auth, "verify_oidc_id_token", lambda token, nonce: True)
    monkeypatch.setattr(sso_auth, "find_sso_allowlist", lambda username, keycloak_id="": None)
    monkeypatch.setattr(
        sso_auth,
        "revoke_unallowlisted_broker_user",
        lambda keycloak_id, username="": revoked.append((keycloak_id, username)),
    )
    session = {
        "sso_state": "abc",
        "sso_nonce": "nonce-1",
        "sso_code_verifier": "ver",
        "sso_alias": "corp",
        "sso_redirect_uri": "http://localhost:1337/auth/sso/callback",
    }
    target, error = sso_auth.complete_sso_callback(session, {"state": "abc", "code": "x"})
    assert target == "/login"
    assert error == "not_allowlisted"
    assert revoked == [("kc-evil", "mallory")]


def test_sso_callback_uses_email_when_preferred_username_missing(monkeypatch):
    seen = []
    monkeypatch.setattr(
        sso_auth,
        "authorization_code_grant",
        lambda code, redirect_uri, verifier: {
            "status": "ok",
            "id_token": "header.payload.sig",
            "claims": {"email": "jane@gmail.com", "sub": "kc-google"},
            "id_claims": {"email": "jane@gmail.com", "sub": "kc-google"},
            "realm_roles": [],
        },
    )
    monkeypatch.setattr(sso_auth, "verify_oidc_id_token", lambda token, nonce: True)
    monkeypatch.setattr(
        sso_auth,
        "find_sso_allowlist",
        lambda username, keycloak_id="": seen.append(username) or None,
    )
    monkeypatch.setattr(sso_auth, "revoke_unallowlisted_broker_user", lambda *args, **kwargs: None)
    session = {
        "sso_state": "abc",
        "sso_nonce": "nonce-1",
        "sso_code_verifier": "ver",
        "sso_alias": "google-oidc",
        "sso_redirect_uri": "http://localhost:1337/auth/sso/callback",
    }
    target, error = sso_auth.complete_sso_callback(session, {"state": "abc", "code": "x"})
    assert target == "/login"
    assert error == "not_allowlisted"
    assert seen == ["jane@gmail.com"]


def test_public_sso_error_is_generic():
    assert sso_auth.public_sso_error("not_allowlisted") == "failed"
    assert sso_auth.public_sso_error("invalid_state") == "failed"
