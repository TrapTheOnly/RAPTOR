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
