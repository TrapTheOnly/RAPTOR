from flask import Flask, session

from app.routes.records import records_bp


def make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(records_bp)
    return app


def _install_permission_bypass(monkeypatch):
    monkeypatch.setattr("app.http.decorators.permission_required.session_has_expired", lambda update_activity=True: False)

    def _has_permission(username, role, permission):
        allowed = {
            ("admin", "create_manual_records"),
            ("manager", "create_manual_records"),
        }
        return (role, permission) in allowed

    monkeypatch.setattr("app.http.decorators.permission_required.user_has_permission", _has_permission)
    monkeypatch.setattr("app.http.decorators.admin_required.session_has_expired", lambda update_activity=True: False)


def test_create_record_route_allows_admin_and_manager(monkeypatch):
    _install_permission_bypass(monkeypatch)
    monkeypatch.setattr(
        "app.routes.records.records_service.create_manual_record",
        lambda data, username: ({"status": "success", "record": {"id": 1, "name": data["name"]}}, 201),
    )

    app = make_app()

    for role in ("admin", "manager"):
        client = app.test_client()
        with client.session_transaction() as flask_session:
            flask_session["logged_in"] = True
            flask_session["username"] = f"{role}1"
            flask_session["user_type"] = role

        response = client.post("/api/records", json={"name": "api.example.com", "ip_address": "10.0.0.1"})
        assert response.status_code == 201
        assert response.get_json()["status"] == "success"


def test_create_record_route_rejects_user_and_pentester(monkeypatch):
    _install_permission_bypass(monkeypatch)
    app = make_app()

    for role in ("user", "pentester"):
        client = app.test_client()
        with client.session_transaction() as flask_session:
            flask_session["logged_in"] = True
            flask_session["username"] = f"{role}1"
            flask_session["user_type"] = role

        response = client.post("/api/records", json={"name": "api.example.com", "ip_address": "10.0.0.1"})
        assert response.status_code == 403
        assert response.get_json()["error"] == "Unauthorized access"


def test_resolve_sync_conflict_route_requires_admin(monkeypatch):
    _install_permission_bypass(monkeypatch)
    monkeypatch.setattr(
        "app.routes.records.records_service.resolve_sync_conflict",
        lambda record_id, username: ({"status": "success"}, 200),
    )

    app = make_app()

    admin_client = app.test_client()
    with admin_client.session_transaction() as flask_session:
        flask_session["logged_in"] = True
        flask_session["username"] = "admin1"
        flask_session["user_type"] = "admin"
    assert admin_client.post("/api/records/5/resolve-sync-conflict").status_code == 200

    manager_client = app.test_client()
    with manager_client.session_transaction() as flask_session:
        flask_session["logged_in"] = True
        flask_session["username"] = "manager1"
        flask_session["user_type"] = "manager"
    assert manager_client.post("/api/records/5/resolve-sync-conflict").status_code == 403
