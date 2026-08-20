from flask import Flask, session

from app.routes.llm import llm_bp


def make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(llm_bp)
    return app


def test_list_connections_masks_secrets(monkeypatch):
    monkeypatch.setattr("app.http.decorators.admin_required.session_has_expired", lambda update_activity=True: False)
    monkeypatch.setattr(
        "app.routes.llm.connections_service.list_connections_service",
        lambda: (
            {
                "connections": [
                    {
                        "id": 4,
                        "type": "openai",
                        "display_name": "OpenAI",
                        "config": {"api_key": "••••••••"},
                    }
                ]
            },
            200,
        ),
    )
    app = make_app()
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["logged_in"] = True
        flask_session["username"] = "admin1"
        flask_session["user_type"] = "admin"
    response = client.get("/admin/llm/connections")
    assert response.status_code == 200
    token = response.get_json()["connections"][0]["config"]["api_key"]
    assert token == "••••••••"
    assert "sk-" not in token


def test_local_status_proxy(monkeypatch):
    monkeypatch.setattr("app.http.decorators.admin_required.session_has_expired", lambda update_activity=True: False)
    monkeypatch.setattr(
        "app.routes.llm.get_local_status_service",
        lambda: ({"status": {"state": "not_installed", "ready": False}, "connection": {"type": "local"}}, 200),
    )
    app = make_app()
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["logged_in"] = True
        flask_session["username"] = "admin1"
        flask_session["user_type"] = "admin"
    response = client.get("/admin/llm/local")
    assert response.status_code == 200
    assert response.get_json()["status"]["state"] == "not_installed"
