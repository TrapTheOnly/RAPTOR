from app.services import keycloak_identity_service as identity
from app.integrations.keycloak.client import decode_access_token
from app.integrations.keycloak.constants import role_from_realm_roles, composite_for_role


def test_role_from_realm_roles_prefers_highest():
    assert role_from_realm_roles(["raptor-access", "raptor-user", "raptor-manager"]) == "manager"
    assert role_from_realm_roles(["raptor-pentester", "raptor-access"]) == "pentester"
    assert role_from_realm_roles([]) == "user"


def test_composite_for_role():
    assert composite_for_role("pentester") == "raptor-pentester"
    assert composite_for_role("unknown") == "raptor-user"


def test_decode_access_token_reads_roles():
    import base64
    import json

    payload = {
        "sub": "abc",
        "realm_access": {"roles": ["raptor-access", "raptor-user"]},
        "resource_access": {"raptor-login": {"roles": ["view_dashboard"]}},
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    token = f"header.{encoded}.sig"
    claims = decode_access_token(token)
    assert claims["sub"] == "abc"
    assert "raptor-access" in claims["realm_access"]["roles"]


def test_search_directory_users_filters_service_accounts(monkeypatch):
    class FakeClient:
        def search_users(self, query, max_results=50):
            return [
                {"username": "service-account-raptor-backend", "email": "", "id": "1"},
                {
                    "username": "jane",
                    "email": "jane@example.com",
                    "firstName": "Jane",
                    "lastName": "Doe",
                    "id": "2",
                    "federationLink": "ldap-comp",
                },
            ]

        def find_user(self, username):
            return None

    monkeypatch.delenv("LDAP_SERVER", raising=False)
    monkeypatch.setattr(identity, "_client", lambda: FakeClient())
    results = identity.search_directory_users("jane")
    assert len(results) == 1
    assert results[0]["username"] == "jane"
    assert results[0]["full_name"] == "Jane Doe"
    assert results[0]["auth_type"] == "ldap"
    assert results[0]["source"] == "LDAP"


def test_verify_service_account_secret_requires_scope(monkeypatch):
    monkeypatch.setattr(
        identity,
        "client_credentials_grant",
        lambda client_id, secret: ({"client_roles": ["records.read"]}, 200),
    )
    assert identity.verify_service_account_secret("svc-reader", "secret", "records.read") is True
    assert identity.verify_service_account_secret("svc-reader", "secret", "pentests.write") is False


def test_assign_raptor_roles_uses_access_and_composite(monkeypatch):
    assigned = {}

    class FakeClient:
        def get_realm_role(self, name):
            return {"name": name}

        def get_client_by_client_id(self, client_id):
            return {"id": "login-uuid", "clientId": client_id}

        def ensure_client_role(self, login_uuid, name):
            return {"name": name, "containerId": login_uuid}

        def replace_user_raptor_realm_roles(self, user_id, roles):
            assigned["realm"] = [row["name"] for row in roles]
            assigned["user_id"] = user_id

        def replace_user_client_roles(self, user_id, login_uuid, roles):
            assigned["client"] = [row["name"] for row in roles]
            assigned["login_uuid"] = login_uuid

    extras = identity.assign_raptor_roles(FakeClient(), "user-1", "pentester", ["view_dashboard"])
    assert assigned["user_id"] == "user-1"
    assert "raptor-access" in assigned["realm"]
    assert "raptor-pentester" in assigned["realm"]
    assert extras == ["view_dashboard"]
    assert assigned["client"] == ["view_dashboard"]


def test_search_directory_falls_back_to_ldap(monkeypatch):
    class FakeClient:
        def search_users(self, query, max_results=50):
            raise RuntimeError("keycloak down")

        def find_user(self, username):
            raise RuntimeError("keycloak down")

    monkeypatch.setenv("LDAP_SERVER", "ldap.example.com")
    monkeypatch.setattr(identity, "_client", lambda: FakeClient())

    import app.integrations.ldap.client as ldap_client

    monkeypatch.setattr(
        ldap_client,
        "search_ldap_users",
        lambda query: [
            {
                "username": "jane",
                "email": "jane@example.com",
                "full_name": "Jane Doe",
                "distinguished_name": "CN=Jane",
            }
        ],
    )
    results = identity.search_directory_users("jane")
    assert results[0]["username"] == "jane"
    assert results[0]["source"] == "LDAP"


def test_search_directory_merges_exact_username_import(monkeypatch):
    class FakeClient:
        def search_users(self, query, max_results=50):
            return [{"username": "jane.local", "email": "local@example.com", "id": "1"}]

        def find_user(self, username):
            if username == "jane":
                return {
                    "username": "jane",
                    "email": "jane@example.com",
                    "id": "ldap-1",
                    "federationLink": "ldap-comp",
                    "firstName": "Jane",
                    "lastName": "Doe",
                }
            return None

    monkeypatch.delenv("LDAP_SERVER", raising=False)
    monkeypatch.setattr(identity, "_client", lambda: FakeClient())
    results = {row["username"]: row for row in identity.search_directory_users("jane")}
    assert "jane" in results
    assert results["jane"]["auth_type"] == "ldap"
    assert "jane.local" in results


def test_auth_type_from_keycloak_user():
    assert identity.auth_type_from_keycloak_user({"username": "alice", "federationLink": "abc"}) == "ldap"
    assert identity.auth_type_from_keycloak_user({"username": "alice"}) == "local"
    assert (
        identity.auth_type_from_keycloak_user(
            {"username": "alice"},
            [{"identityProvider": "corp-oidc"}],
            [{"alias": "corp-oidc", "providerId": "oidc"}],
        )
        == "oidc"
    )
    assert (
        identity.auth_type_from_keycloak_user(
            {"username": "alice"},
            [{"identityProvider": "corp-adfs"}],
            [{"alias": "corp-adfs", "providerId": "saml"}],
        )
        == "saml"
    )


def test_provision_ldap_user_allowlists_existing_federated_user(monkeypatch):
    created = []
    updated = {}

    class FakeClient:
        def find_user(self, username):
            return {
                "id": "kc-jane",
                "username": username,
                "email": "jane@example.com",
                "federationLink": "ldap-comp",
                "firstName": "Jane",
                "lastName": "Doe",
                "requiredActions": ["VERIFY_PROFILE"],
            }

        def create_user(self, representation):
            created.append(representation)
            return "should-not-create"

        def update_user(self, user_id, representation):
            updated["id"] = user_id
            updated["body"] = representation

        def get_user(self, user_id):
            return {
                "id": user_id,
                "username": "jane",
                "email": "jane@example.com",
                "federationLink": "ldap-comp",
                "firstName": "Jane",
                "lastName": "Doe",
            }

        def get_federated_identities(self, user_id):
            return []

        def list_identity_providers(self):
            return []

        def get_realm_role(self, name):
            return {"name": name}

        def get_client_by_client_id(self, client_id):
            return {"id": "login-uuid", "clientId": client_id}

        def ensure_client_role(self, login_uuid, name):
            return {"name": name}

        def replace_user_raptor_realm_roles(self, user_id, roles):
            return None

        def replace_user_client_roles(self, user_id, login_uuid, roles):
            return None

    monkeypatch.setattr(identity, "_client", lambda: FakeClient())
    monkeypatch.setattr(identity, "upsert_identity_cache", lambda **kwargs: cached.update(kwargs))
    cached = {}
    user_id = identity.provision_ldap_user("jane", "jane@example.com", "user", [])
    assert user_id == "kc-jane"
    assert created == []
    assert updated["id"] == "kc-jane"
    assert "VERIFY_PROFILE" not in updated["body"]["requiredActions"]
    assert cached["auth_type"] == "ldap"
    assert cached["keycloak_id"] == "kc-jane"


def test_provision_ldap_user_missing_identity_raises(monkeypatch):
    class FakeClient:
        def find_user(self, username):
            return None

        def create_user(self, representation):
            raise AssertionError("must not create a local password user")

    monkeypatch.setattr(identity, "_client", lambda: FakeClient())
    try:
        identity.provision_ldap_user("missing", "missing@example.com", "user", [])
        assert False, "expected LookupError"
    except LookupError as exc:
        assert "missing" in str(exc)


def test_provision_sso_placeholder_creates_keycloak_user_without_email(monkeypatch):
    created = []
    assigned = []
    cached = {}

    class FakeClient:
        def find_user(self, username):
            return None

        def create_user(self, representation):
            created.append(representation)
            return "kc-sso-1"

        def get_realm_role(self, name):
            return {"name": name}

        def get_client_by_client_id(self, client_id):
            return {"id": "login-uuid", "clientId": client_id}

        def ensure_client_role(self, login_uuid, name):
            return {"name": name}

        def replace_user_raptor_realm_roles(self, user_id, roles):
            assigned.append(("realm", user_id, [row["name"] for row in roles]))

        def replace_user_client_roles(self, user_id, login_uuid, roles):
            return None

    monkeypatch.setattr(identity, "_client", lambda: FakeClient())
    monkeypatch.setattr(identity, "add_allowed_user", lambda **kwargs: cached.update(kwargs))
    identity.provision_sso_placeholder("jsmith", "jsmith@example.com", "user", [], auth_type="oidc")
    assert created[0]["username"] == "jsmith"
    assert created[0]["email"] == "jsmith@sso.invalid"
    assert created[0]["firstName"] == "jsmith"
    assert created[0]["lastName"] == "SSO"
    assert cached["email"] == "jsmith@example.com"
    assert cached["keycloak_id"] == "kc-sso-1"
    assert cached["auth_type"] == "oidc"
    assert assigned[0][0] == "realm"


def test_sso_placeholder_email_username_stays_valid(monkeypatch):
    created = []

    class FakeClient:
        def find_user(self, username):
            return None

        def create_user(self, representation):
            created.append(representation)
            return "kc-google-1"

        def get_realm_role(self, name):
            return {"name": name}

        def get_client_by_client_id(self, client_id):
            return {"id": "login-uuid", "clientId": client_id}

        def ensure_client_role(self, login_uuid, name):
            return {"name": name}

        def replace_user_raptor_realm_roles(self, user_id, roles):
            return None

        def replace_user_client_roles(self, user_id, login_uuid, roles):
            return None

    monkeypatch.setattr(identity, "_client", lambda: FakeClient())
    monkeypatch.setattr(identity, "add_allowed_user", lambda **kwargs: None)
    identity.provision_sso_placeholder(
        "ismail.eyyub@gmail.com",
        "ismail.eyyub@gmail.com",
        "pentester",
        [],
        auth_type="oidc",
    )
    assert created[0]["username"] == "ismail.eyyub@gmail.com"
    assert created[0]["email"] == "ismail.eyyub.gmail.com@sso.invalid"
    assert created[0]["email"].count("@") == 1


def test_revoke_unallowlisted_broker_user_deletes_without_access(monkeypatch):
    deleted = []

    class FakeClient:
        def get_user(self, user_id):
            return {"id": user_id, "username": "mallory"}

        def find_user(self, username):
            return None

        def get_user_realm_roles(self, user_id):
            return [{"name": "default-roles-raptor"}]

        def delete_user(self, user_id):
            deleted.append(user_id)

        def update_user(self, user_id, representation):
            raise AssertionError("should delete rather than disable")

    monkeypatch.setattr(identity, "_client", lambda: FakeClient())
    identity.revoke_unallowlisted_broker_user("kc-evil", "mallory")
    assert deleted == ["kc-evil"]


def test_revoke_unallowlisted_broker_user_leaves_ldap_and_access(monkeypatch):
    deleted = []

    class FakeClient:
        def get_user(self, user_id):
            if user_id == "ldap-1":
                return {"id": user_id, "username": "jane", "federationLink": "ldap"}
            return {"id": user_id, "username": "alice"}

        def get_user_realm_roles(self, user_id):
            return [{"name": "raptor-access"}]

        def delete_user(self, user_id):
            deleted.append(user_id)

    monkeypatch.setattr(identity, "_client", lambda: FakeClient())
    identity.revoke_unallowlisted_broker_user("ldap-1", "jane")
    identity.revoke_unallowlisted_broker_user("kc-alice", "alice")
    assert deleted == []
