from pathlib import Path

from app.services import keycloak_bootstrap_service as bootstrap


def test_bootstrap_skips_when_flag_set(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_BOOTSTRAP_SKIP", "true")
    called = []
    monkeypatch.setattr(bootstrap, "KeycloakClient", lambda: called.append("client"))
    bootstrap.bootstrap_keycloak()
    assert called == []


def test_bootstrap_skips_worker(monkeypatch):
    monkeypatch.delenv("KEYCLOAK_BOOTSTRAP_SKIP", raising=False)
    monkeypatch.setenv("RAPTOR_ROLE", "worker")
    called = []
    monkeypatch.setattr(bootstrap, "KeycloakClient", lambda: called.append("client"))
    bootstrap.bootstrap_keycloak()
    assert called == []


def test_ldap_users_dn_from_domain(monkeypatch):
    monkeypatch.delenv("LDAP_USERS_DN", raising=False)
    monkeypatch.setenv("LDAP_DOMAIN", "example.com")
    assert bootstrap._ldap_users_dn() == "DC=example,DC=com"


def test_ldap_users_dn_override(monkeypatch):
    monkeypatch.setenv("LDAP_USERS_DN", "OU=People,DC=example,DC=com")
    monkeypatch.setenv("LDAP_DOMAIN", "example.com")
    assert bootstrap._ldap_users_dn() == "OU=People,DC=example,DC=com"


def test_ldap_connection_candidates_try_both_when_unspecified(monkeypatch):
    monkeypatch.delenv("LDAP_USE_SSL", raising=False)
    monkeypatch.delenv("LDAP_START_TLS", raising=False)
    monkeypatch.setenv("LDAP_SERVER", "dc.example.com")
    urls = [item["connectionUrl"] for item in bootstrap._ldap_connection_candidates()]
    assert "ldaps://dc.example.com" in urls
    assert "ldap://dc.example.com" in urls


def test_ldap_connection_url_keeps_explicit_scheme(monkeypatch):
    monkeypatch.setenv("LDAP_SERVER", "ldap://dc.example.com")
    assert bootstrap._ldap_connection_candidates() == [
        {"connectionUrl": "ldap://dc.example.com", "startTls": "false"}
    ]


def test_idp_config_from_env_oidc(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_IDP_ALIAS", "corp-oidc")
    monkeypatch.setenv("KEYCLOAK_IDP_PROVIDER", "oidc")
    monkeypatch.setenv("KEYCLOAK_IDP_CLIENT_ID", "raptor")
    monkeypatch.setenv("KEYCLOAK_IDP_CLIENT_SECRET", "secret")
    monkeypatch.setenv("KEYCLOAK_IDP_ISSUER", "https://idp.example.com")
    payload = bootstrap._idp_config_from_env()
    assert payload["alias"] == "corp-oidc"
    assert payload["providerId"] == "oidc"
    assert payload["config"]["issuer"] == "https://idp.example.com"
    assert payload["config"]["hideOnLoginPage"] == "true"


def test_idp_config_from_env_skips_without_alias(monkeypatch):
    monkeypatch.delenv("KEYCLOAK_IDP_ALIAS", raising=False)
    monkeypatch.delenv("KEYCLOAK_IDP_PROVIDER", raising=False)
    assert bootstrap._idp_config_from_env() is None


def test_ensure_ldap_disables_when_unreachable(monkeypatch):
    from app.integrations.keycloak.client import KeycloakAdminError

    disabled = []

    class FakeClient:
        def test_ldap_connection(self, *args, **kwargs):
            raise KeycloakAdminError("unreachable", status_code=400)

        def set_ldap_federation_enabled(self, enabled):
            disabled.append(enabled)
            return True

        def ensure_ldap_federation(self, config, realm_id):
            raise AssertionError("must not register unreachable LDAP")

    monkeypatch.setenv("LDAP_SERVER", "dc.example.com")
    monkeypatch.setenv("LDAP_DOMAIN", "example.com")
    monkeypatch.setenv("LDAP_USER", "bind")
    monkeypatch.setenv("LDAP_PASS", "x")
    bootstrap._ensure_ldap(FakeClient())
    assert disabled == [False]


def test_compose_files_include_keycloak_service():
    root = Path(__file__).resolve().parents[3]
    for name in ("docker-compose.dev.yml", "docker-compose.prod.yml"):
        text = (root / name).read_text(encoding="utf-8")
        assert "keycloak:" in text
        assert "CREATE SCHEMA IF NOT EXISTS keycloak" in text
        assert "KEYCLOAK_LOGIN_CLIENT_SECRET" in text
        assert "LDAP_TRUSTSTORE" in text
        assert "KEYCLOAK_IDP_ALIAS" in text
        assert "raptor-realm.json" in text
        assert "KC_DB_SCHEMA=keycloak" in text
    realm = (root / "deploy/keycloak/raptor-realm.json").read_text(encoding="utf-8")
    assert '"realm": "raptor"' in realm
    assert "raptor-login" in realm
    assert "raptor-backend" in realm
    assert "raptor-access" in realm
