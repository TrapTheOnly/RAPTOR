from app.services import auth_service


class FakeSession(dict):
    def __init__(self):
        super().__init__()
        self.permanent = False


def test_login_admin_password_reset_required(monkeypatch):
    monkeypatch.setattr(auth_service, "get_allowed_user_for_login", lambda username: None)
    monkeypatch.setattr(
        auth_service,
        "password_grant",
        lambda username, password: {"status": "reset_required"},
    )
    monkeypatch.setattr(auth_service, "user_has_required_action", lambda username, action="UPDATE_PASSWORD": True)
    monkeypatch.setattr(auth_service, "get_user_permissions", lambda username, role: {"view_dashboard"})

    session_obj = FakeSession()
    payload, status = auth_service.login(
        {"username": auth_service.ADMIN_USERNAME, "password": "secret"},
        session_obj,
    )

    assert status == 200
    assert payload["status"] == "password_reset_required"
    assert session_obj["reset_required"] is True
    assert session_obj["logged_in"] is False


def test_login_requires_raptor_access(monkeypatch):
    monkeypatch.setattr(auth_service, "get_allowed_user_for_login", lambda username: None)
    monkeypatch.setattr(
        auth_service,
        "password_grant",
        lambda username, password: {
            "status": "ok",
            "realm_roles": ["raptor-user"],
            "client_roles": [],
            "claims": {"sub": "abc"},
        },
    )

    payload, status = auth_service.login(
        {"username": "alice", "password": "secret"},
        FakeSession(),
    )
    assert status == 401
    assert payload == {"error": "Invalid credentials"}


def test_login_success_sets_session(monkeypatch):
    cached = ("alice", "pentester", "local", 0, "kc-1")
    monkeypatch.setattr(auth_service, "get_allowed_user_for_login", lambda username: cached)
    monkeypatch.setattr(
        auth_service,
        "password_grant",
        lambda username, password: {
            "status": "ok",
            "realm_roles": ["raptor-access", "raptor-pentester"],
            "client_roles": ["view_dashboard"],
            "claims": {"sub": "kc-1"},
        },
    )
    monkeypatch.setattr(auth_service, "cache_from_login", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_service, "auth_type_for_username", lambda username: "ldap")
    monkeypatch.setattr(auth_service, "get_user_permissions", lambda username, role: {"view_pentest_page"})
    monkeypatch.setattr(auth_service, "_audit_login", lambda username: None)
    monkeypatch.setattr(auth_service, "initialize_session_tracking", lambda: None)

    session_obj = FakeSession()
    payload, status = auth_service.login({"username": "alice", "password": "secret"}, session_obj)
    assert status == 200
    assert payload["status"] == "logged_in"
    assert payload["user_type"] == "pentester"
    assert session_obj["logged_in"] is True


def test_login_retries_after_incomplete_profile(monkeypatch):
    grants = [
        {"status": "reset_required"},
        {
            "status": "ok",
            "realm_roles": ["raptor-access", "raptor-user"],
            "client_roles": [],
            "claims": {"sub": "kc-2"},
        },
    ]
    prepared = []
    monkeypatch.setattr(auth_service, "get_allowed_user_for_login", lambda username: None)
    monkeypatch.setattr(auth_service, "password_grant", lambda username, password: grants.pop(0))
    monkeypatch.setattr(auth_service, "user_has_required_action", lambda username, action="UPDATE_PASSWORD": False)
    monkeypatch.setattr(auth_service, "prepare_user_for_raptor_login", lambda username: prepared.append(username))
    monkeypatch.setattr(auth_service, "auth_type_for_username", lambda username: "ldap")
    monkeypatch.setattr(auth_service, "cache_from_login", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_service, "get_user_permissions", lambda username, role: {"view_dashboard"})
    monkeypatch.setattr(auth_service, "_audit_login", lambda username: None)
    monkeypatch.setattr(auth_service, "initialize_session_tracking", lambda: None)

    session_obj = FakeSession()
    payload, status = auth_service.login({"username": "jane", "password": "secret"}, session_obj)
    assert status == 200
    assert payload["status"] == "logged_in"
    assert prepared == ["jane"]
    assert session_obj["logged_in"] is True


def test_login_rejects_service_accounts(monkeypatch):
    cached = ("svc.reader", "user", "service", 1, "kc-svc")
    monkeypatch.setattr(auth_service, "get_allowed_user_for_login", lambda username: cached)
    called = []
    monkeypatch.setattr(
        auth_service,
        "password_grant",
        lambda username, password: called.append(username) or {"status": "ok"},
    )

    payload, status = auth_service.login(
        {"username": "svc.reader", "password": "raptor_sk_secret"},
        FakeSession(),
    )
    assert status == 401
    assert payload == {"error": "Invalid credentials"}
    assert called == []


def test_session_status_logged_out_by_default():
    payload, status = auth_service.session_status(FakeSession())
    assert status == 401
    assert payload == {"status": "logged_out"}


def test_admin_reset_password_returns_permissions(monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "reset_admin_password",
        lambda new_password: ({"status": "ok"}, 200),
    )
    monkeypatch.setattr(
        auth_service,
        "get_user_permissions",
        lambda username, role: {"view_dashboard", "view_records"},
    )
    monkeypatch.setattr(auth_service, "initialize_session_tracking", lambda: None)

    session_obj = FakeSession()
    session_obj["reset_required"] = True
    session_obj["username"] = auth_service.ADMIN_USERNAME

    payload, status = auth_service.admin_reset_password(
        {"new_password": "StrongPassword!123"},
        session_obj,
    )

    assert status == 200
    assert payload["status"] == "logged_in"
    assert payload["user_type"] == "admin"
    assert set(payload["permissions"]) == {"view_dashboard", "view_records"}


def test_user_reset_password_returns_permissions(monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "validate_password_nist",
        lambda new_password, username=None: (True, ""),
    )
    monkeypatch.setattr(auth_service, "set_user_password", lambda username, password, temporary=False: None)
    monkeypatch.setattr(auth_service, "initialize_session_tracking", lambda: None)
    monkeypatch.setattr(
        auth_service,
        "get_user_permissions",
        lambda username, role: {"view_security_dashboard", "modify_pentests"},
    )

    session_obj = FakeSession()
    session_obj["reset_required"] = True
    session_obj["username"] = "tester1"
    session_obj["user_type"] = "pentester"

    payload, status = auth_service.user_reset_password(
        {"new_password": "NewStrongPass!456"},
        session_obj,
    )

    assert status == 200
    assert payload["status"] == "logged_in"
    assert payload["username"] == "tester1"
    assert payload["user_type"] == "pentester"
    assert set(payload["permissions"]) == {"view_security_dashboard", "modify_pentests"}
