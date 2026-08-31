from flask import Flask

from app.routes.app_program import app_program_bp


def make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(app_program_bp)
    return app


def login(client):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["username"] = "ada"
        session["user_type"] = "pentester"
        session["reset_required"] = False


def _allow(monkeypatch):
    monkeypatch.setattr("app.http.decorators.permission_required.session_has_expired", lambda **kwargs: False)
    monkeypatch.setattr(
        "app.http.decorators.permission_required.drop_invalid_identity_session",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(
        "app.http.decorators.permission_required.user_has_permission",
        lambda *args, **kwargs: True,
    )


def test_list_engagements_route(monkeypatch):
    _allow(monkeypatch)
    monkeypatch.setattr(
        "app.services.engagements_service.list_engagements",
        lambda app_id, wave_id, username, role: (
            {"engagements": [{"id": "scan:12", "title": "Northwind auth sweep"}]},
            200,
        ),
    )
    client = make_app().test_client()
    login(client)
    response = client.get("/api/apps/1/waves/9/engagements")
    assert response.status_code == 200
    assert response.get_json()["engagements"][0]["id"] == "scan:12"


def test_accept_engagement_route(monkeypatch):
    _allow(monkeypatch)
    monkeypatch.setattr(
        "app.services.engagements_service.accept_proposal",
        lambda app_id, wave_id, job_id, username, role: (
            {"finding": {"id": "f-1"}},
            201,
        ),
    )
    client = make_app().test_client()
    login(client)
    response = client.post("/api/apps/1/waves/9/engagements/burp/4/accept")
    assert response.status_code == 201
    assert response.get_json()["finding"]["id"] == "f-1"


def test_accept_proposal_route(monkeypatch):
    _allow(monkeypatch)
    monkeypatch.setattr(
        "app.services.engagements_service.accept_scanner_proposal",
        lambda app_id, wave_id, proposal_id, username, role: (
            {"finding": {"id": "f-sql"}},
            201,
        ),
    )
    client = make_app().test_client()
    login(client)
    response = client.post("/api/apps/1/waves/9/engagements/proposals/19/accept")
    assert response.status_code == 201
    assert response.get_json()["finding"]["id"] == "f-sql"
