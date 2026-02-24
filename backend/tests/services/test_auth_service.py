import bcrypt
from app.services import auth_service


class FakeSession(dict):
    def __init__(self):
        super().__init__()
        self.permanent = False


def test_login_returns_lockout_when_active(monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_login_lockout_status",
        lambda username: {"locked": True, "retry_after_seconds": 90},
    )

    payload, status = auth_service.login(
        {"username": "user1", "password": "secret"},
        FakeSession(),
    )

    assert status == 429
    assert payload["error"] == "Too many failed login attempts. Try again later."


def test_login_admin_password_reset_required(monkeypatch):
    monkeypatch.setattr(auth_service, "get_login_lockout_status", lambda username: {"locked": False})
    monkeypatch.setattr(auth_service, "get_allowed_user_for_login", lambda username: None)
    monkeypatch.setattr(auth_service, "admin_login", lambda username, password: True)
    monkeypatch.setattr(auth_service, "admin_requires_password_reset", lambda username: True)
    monkeypatch.setattr(auth_service, "get_user_permissions", lambda username, role: {"view_dashboard"})
    monkeypatch.setattr(auth_service, "clear_login_lockout_state", lambda username: None)

    session_obj = FakeSession()
    payload, status = auth_service.login(
        {"username": auth_service.ADMIN_USERNAME, "password": "secret"},
        session_obj,
    )

    assert status == 200
    assert payload["status"] == "password_reset_required"
    assert session_obj["reset_required"] is True
    assert session_obj["logged_in"] is False


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
    monkeypatch.setattr(
        auth_service,
        "get_user_password",
        lambda username: bcrypt.hashpw("TempPass!123".encode(), bcrypt.gensalt()),
    )
    monkeypatch.setattr(auth_service, "update_local_user_password", lambda username, hashed: 1)
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
