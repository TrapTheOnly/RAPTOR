from app.integrations.keycloak.constants import (
    is_supported_sso_provider,
    keycloak_public_url,
    login_redirect_uris,
    raptor_public_url,
    sso_callback_url,
    sso_protocol,
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


def test_connection_public_view_ignores_placeholder_secret():
    view = sso_settings.connection_public_view(
        {
            "alias": "corp",
            "providerId": "oidc",
            "config": {"clientSecret": "**********"},
        }
    )
    assert view["has_client_secret"] is False


def test_ensure_idp_skips_existing(monkeypatch):
    calls = []

    class FakeClient:
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
    assert sso_auth.identity_session_valid({"logged_in": True}) is True
    assert sso_auth.drop_invalid_identity_session({}) is False
