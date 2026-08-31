from flask import Flask

from app.routes.burp import burp_bp


def make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(burp_bp)
    return app


def login(client, role="pentester", username="ada"):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["username"] = username
        session["user_type"] = role
        session["reset_required"] = False


def test_enroll_and_ingest_require_token():
    app = make_app()
    client = app.test_client()
    assert client.post("/burp/v1/enroll", json={}).status_code == 400
    assert client.post("/burp/v1/heartbeat", json={}).status_code == 401
    assert client.post("/burp/v1/ingest", json={"events": []}).status_code == 401
    assert client.post("/burp/v1/auth-template", json={}).status_code == 401
    assert client.post("/burp/v1/jwt", json={}).status_code == 401
    assert client.get("/burp/v1/drafts").status_code == 401
    assert client.post("/burp/v1/evidence", json={}).status_code == 401


def test_mint_token_uses_session(monkeypatch):
    monkeypatch.setattr("app.http.decorators.permission_required.session_has_expired", lambda **kwargs: False)
    monkeypatch.setattr("app.http.decorators.permission_required.drop_invalid_identity_session", lambda *_a, **_k: False)
    monkeypatch.setattr("app.http.decorators.permission_required.user_has_permission", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.services.burp_service.mint_wave_token",
        lambda app_id, wave_id, username, role: ({"token": "raptor_burp_enroll_x", "wave_id": wave_id}, 201),
    )
    app = make_app()
    client = app.test_client()
    login(client)
    response = client.post("/api/apps/1/waves/9/burp-token", json={})
    assert response.status_code == 201
    assert response.get_json()["token"].startswith("raptor_burp_enroll_")


def test_analyze_uses_session(monkeypatch):
    monkeypatch.setattr("app.http.decorators.permission_required.session_has_expired", lambda **kwargs: False)
    monkeypatch.setattr("app.http.decorators.permission_required.drop_invalid_identity_session", lambda *_a, **_k: False)
    monkeypatch.setattr("app.http.decorators.permission_required.user_has_permission", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.services.burp_analyze.queue_analyze_job",
        lambda app_id, wave_id, username, role: ({"job_id": 21, "engagement_id": "burp:21", "status": "queued"}, 202),
    )
    app = make_app()
    client = app.test_client()
    login(client)
    response = client.post("/api/apps/1/waves/9/burp/analyze", json={})
    assert response.status_code == 202
    assert response.get_json()["engagement_id"] == "burp:21"


def test_service_api_key_header_is_not_accepted():
    app = make_app()
    client = app.test_client()
    response = client.post(
        "/burp/v1/heartbeat",
        json={},
        headers={"X-API-Key": "raptor_sk_not_this"},
    )
    assert response.status_code == 401
