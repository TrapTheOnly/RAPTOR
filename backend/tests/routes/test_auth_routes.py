from flask import Flask

from app.routes.auth import auth_bp


def make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(auth_bp)
    return app


def test_login_no_payload_returns_400():
    app = make_app()
    client = app.test_client()

    response = client.post("/login")
    assert response.status_code == 400
    assert response.get_json() == {"error": "No data provided"}


def test_session_extend_logged_out_returns_401():
    app = make_app()
    client = app.test_client()

    response = client.post("/session/extend")
    assert response.status_code == 401
    assert response.get_json() == {"status": "logged_out"}


def test_sso_providers_returns_list(monkeypatch):
    monkeypatch.setattr(
        "app.routes.auth.list_login_providers",
        lambda: ({"providers": [{"alias": "corp", "display_name": "Corp", "protocol": "oidc"}]}, 200),
    )
    app = make_app()
    client = app.test_client()
    response = client.get("/auth/sso/providers")
    assert response.status_code == 200
    assert response.get_json()["providers"][0]["alias"] == "corp"


def test_sso_start_redirects_on_error(monkeypatch):
    monkeypatch.setattr(
        "app.routes.auth.authorization_url",
        lambda alias, session_obj: (None, "unsupported"),
    )
    app = make_app()
    client = app.test_client()
    response = client.get("/auth/sso/google/start", follow_redirects=False)
    assert response.status_code in {302, 303}
    assert "sso_error=failed" in response.headers["Location"]
    assert "unsupported" not in response.headers["Location"]


def test_sso_callback_hides_allowlist_reason(monkeypatch):
    monkeypatch.setattr(
        "app.routes.auth.complete_sso_callback",
        lambda session_obj, args: ("/login", "not_allowlisted"),
    )
    app = make_app()
    client = app.test_client()
    response = client.get("/auth/sso/callback?code=x&state=y", follow_redirects=False)
    assert response.status_code in {302, 303}
    assert "sso_error=failed" in response.headers["Location"]
    assert "not_allowlisted" not in response.headers["Location"]
