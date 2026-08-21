from flask import Flask

from app.http.decorators import permission_required as permission_decorator
from app.services.offsec import offsec_generated_reports as generated_reports


DISABLED_TEMPLATE = {
    "id": 9,
    "key": "disabled-template",
    "name": "Disabled",
    "description": "",
    "template_json": "{}",
    "enabled": 0,
}


def _make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.add_url_rule(
        "/pentest/<int:record_id>/generate-report",
        methods=["POST"],
        view_func=generated_reports.generate_report,
    )
    return app


def _set_logged_in_session(client, username, role):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = username
        sess["user_type"] = role


class _Cursor:
    def __init__(self, template_row):
        self.template_row = template_row
        self._last = ""

    def execute(self, query, params=None):
        self._last = " ".join(str(query).split()).lower()
        return self

    def fetchone(self):
        if "from report_templates" in self._last:
            return self.template_row
        if "generated_report_file" in self._last:
            return None
        return None


class _Conn:
    def __init__(self, template_row):
        self.cursor_obj = _Cursor(template_row)
        self.row_factory = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        return None


def _stub_disabled_template_generate(monkeypatch, granted_permissions):
    monkeypatch.setattr(permission_decorator, "session_has_expired", lambda update_activity=True: False)
    monkeypatch.setattr(
        permission_decorator,
        "user_has_permission",
        lambda username, role, permission: permission == "export_pentests" or permission in granted_permissions,
    )
    monkeypatch.setattr(
        generated_reports,
        "user_has_permission",
        lambda username, role, permission: permission in granted_permissions,
    )
    monkeypatch.setattr(
        generated_reports,
        "get_record_details_internal",
        lambda record_id: {"id": record_id, "name": "host", "ip_address": "1.1.1.1", "source": "manual"},
    )
    monkeypatch.setattr(generated_reports, "get_access_role_for_user", lambda *args, **kwargs: "owner")
    monkeypatch.setattr(
        generated_reports,
        "get_pentest_capabilities",
        lambda access_role: {"can_generate_reports": True},
    )
    monkeypatch.setattr(generated_reports, "get_db_connection", lambda _: _Conn(DISABLED_TEMPLATE))
    monkeypatch.setattr(
        generated_reports,
        "bind_report_template_logo_for_template",
        lambda cursor, template_id, definition: (definition, None),
    )
    monkeypatch.setattr(generated_reports, "load_enabled_checklist_templates", lambda: [])
    monkeypatch.setattr(generated_reports, "get_pentest_data_internal", lambda record_id: {"record_id": record_id})
    monkeypatch.setattr(generated_reports, "render_pentest_report_pdf", lambda *args, **kwargs: b"%PDF")
    monkeypatch.setattr(generated_reports, "save_report", lambda record_id, content: "reports/1.pdf")
    monkeypatch.setattr("app.services.app_report_service.record_host_export", lambda *args, **kwargs: None)


def test_generate_report_rejects_disabled_template_without_manage_permission(monkeypatch):
    _stub_disabled_template_generate(monkeypatch, granted_permissions=set())
    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "alice", "pentester")

    response = client.post("/pentest/1/generate-report", json={"template_id": 9})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Selected report template is disabled."


def test_generate_report_allows_disabled_template_with_manage_report_templates(monkeypatch):
    _stub_disabled_template_generate(monkeypatch, granted_permissions={"manage_report_templates"})
    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "manager1", "manager")

    response = client.post("/pentest/1/generate-report", json={"template_id": 9})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["template_id"] == 9
    assert payload["message"] == "Report generated successfully."


def test_generate_report_allows_disabled_template_for_admin(monkeypatch):
    _stub_disabled_template_generate(monkeypatch, granted_permissions=set())
    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "awadmin", "admin")

    response = client.post("/pentest/1/generate-report", json={"template_id": 9})

    assert response.status_code == 200
    assert response.get_json()["template_id"] == 9
