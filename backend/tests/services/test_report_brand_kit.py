from flask import Flask

from app.services.report_brand_kit_service import DEFAULT_KIT, apply_brand_kit, get_report_brand_kit


def test_apply_brand_kit_overrides_company_and_ink():
    template = {
        "branding": {
            "company_name": "Old Co",
            "primary_color": "#0B5CAD",
            "logo_url": "",
            "header_text": "Confidential",
        },
        "blocks": [],
    }
    kit = {**DEFAULT_KIT, "company_name": "Raptor", "print_ink": "#067A8A", "logo_url": "/pentest/images/aa.png"}
    next_def = apply_brand_kit(template, kit)
    assert next_def["branding"]["company_name"] == "Raptor"
    assert next_def["branding"]["primary_color"] == "#067A8A"
    assert next_def["branding"]["logo_url"].endswith(".png")
    assert next_def["branding"]["header_text"] == "Confidential"


def test_get_report_brand_kit_route(monkeypatch):
    monkeypatch.setattr(
        "app.http.decorators.permission_required.session_has_expired",
        lambda update_activity=True: False,
    )
    monkeypatch.setattr(
        "app.http.decorators.permission_required.user_has_permission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "app.services.report_brand_kit_service.fetch_brand_kit",
        lambda: dict(DEFAULT_KIT),
    )
    app = Flask(__name__)
    app.secret_key = "test"
    app.add_url_rule("/report-brand-kit", methods=["GET"], view_func=get_report_brand_kit)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["logged_in"] = True
        flask_session["username"] = "admin1"
        flask_session["user_type"] = "admin"
    response = client.get("/report-brand-kit")
    assert response.status_code == 200
    assert response.get_json()["kit"]["print_ink"] == "#067A8A"
