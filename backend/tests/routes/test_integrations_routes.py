from flask import Flask

from app.routes.integrations import integrations_bp


def make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(integrations_bp)
    return app


def login(client, role="admin"):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["username"] = "ada"
        session["user_type"] = role
        session["reset_required"] = False


def test_meta_returns_raptor_fields(monkeypatch):
    monkeypatch.setattr("app.http.decorators.permission_required.session_has_expired", lambda **kwargs: False)
    monkeypatch.setattr("app.http.decorators.permission_required.drop_invalid_identity_session", lambda *_a, **_k: False)
    monkeypatch.setattr("app.http.decorators.permission_required.user_has_permission", lambda *args, **kwargs: True)
    app = make_app()
    client = app.test_client()
    login(client, role="pentester")
    response = client.get("/api/integrations/meta")
    assert response.status_code == 200
    body = response.get_json()
    ids = {item["id"] for item in body["raptor_fields"]}
    assert "title" in ids
    assert "severity" in ids
    assert "impact" in ids
    assert "evidence" in ids
    assert "remediation" in ids
    assert {item["id"] for item in body["kinds"]} == {"jira", "defectdojo"}


def test_preview_and_export_delegate(monkeypatch):
    from app.services import integrations_service

    monkeypatch.setattr("app.http.decorators.permission_required.session_has_expired", lambda **kwargs: False)
    monkeypatch.setattr("app.http.decorators.permission_required.drop_invalid_identity_session", lambda *_a, **_k: False)
    monkeypatch.setattr("app.http.decorators.permission_required.user_has_permission", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        integrations_service,
        "preview_export",
        lambda data: ({"findings": [{"id": "1"}], "ask": []}, 200),
    )
    monkeypatch.setattr(
        integrations_service,
        "export_findings",
        lambda data, username: ({"created": 1, "failed": 0, "results": []}, 200),
    )
    app = make_app()
    client = app.test_client()
    login(client, role="pentester")
    preview = client.post("/api/integrations/preview", json={"template_id": 1, "finding_ids": ["1"]})
    assert preview.status_code == 200
    assert preview.get_json()["findings"][0]["id"] == "1"
    exported = client.post("/api/integrations/export", json={"template_id": 1, "finding_ids": ["1"]})
    assert exported.status_code == 200
    assert exported.get_json()["created"] == 1


def test_jira_already_reported_follows_ticket_url_not_export_history():
    from app.services.integrations_service import _already_at_destination

    history = {"status": "created", "external_url": "http://jira.example/browse/APP-1"}
    assert _already_at_destination("jira", {"ticket_url": ""}, history) is False
    assert _already_at_destination("jira", {"ticket_url": "http://jira.example/browse/APP-1"}, history) is True
    assert _already_at_destination("defectdojo", {"ticket_url": ""}, history) is True
    assert _already_at_destination("defectdojo", {"ticket_url": ""}, None) is False
