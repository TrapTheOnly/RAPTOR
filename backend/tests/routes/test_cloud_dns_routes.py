from flask import Flask, session

from app.routes.cloud_dns import cloud_dns_bp


def make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(cloud_dns_bp)
    return app


def test_list_dns_sources_masks_secrets(monkeypatch):
    monkeypatch.setattr("app.http.decorators.admin_required.session_has_expired", lambda update_activity=True: False)
    monkeypatch.setattr(
        "app.routes.cloud_dns.cloud_dns_service.list_cloud_sources_service",
        lambda: (
            {
                "sources": [
                    {
                        "id": 3,
                        "type": "cloudflare",
                        "display_name": "Prod CF",
                        "config": {"api_token": "••••••••"},
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
    response = client.get("/admin/dns-sources")
    assert response.status_code == 200
    token = response.get_json()["sources"][0]["config"]["api_token"]
    assert token == "••••••••"
    assert "cf_" not in token
