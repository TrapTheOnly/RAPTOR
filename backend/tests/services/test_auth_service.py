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
