import json

from flask import Flask

from app.http.decorators import permission_required as permission_decorator
from app.services.offsec import offsec_pentest


def _make_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.add_url_rule("/pentest/<int:record_id>", methods=["POST"], view_func=offsec_pentest.create_or_update_pentest_data)
    app.add_url_rule(
        "/pentest/<int:record_id>/collaborators",
        methods=["POST"],
        view_func=offsec_pentest.add_pentest_collaborator,
    )
    app.add_url_rule(
        "/pentest/<int:record_id>/collaborators/<string:username>",
        methods=["DELETE"],
        view_func=offsec_pentest.remove_pentest_collaborator,
    )
    return app


def _set_logged_in_session(client, username, role):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = username
        sess["user_type"] = role


class _Cursor:
    def __init__(self):
        self.rowcount = 1
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((" ".join(str(query).split()).lower(), params))
        return self


class _Conn:
    def __init__(self):
        self.cursor_obj = _Cursor()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True


def _allow_permissions(monkeypatch):
    monkeypatch.setattr(permission_decorator, "session_has_expired", lambda update_activity=True: False)
    monkeypatch.setattr(permission_decorator, "user_has_permission", lambda username, role, permission: True)


def test_owner_can_add_collaborator(monkeypatch):
    _allow_permissions(monkeypatch)
    conn = _Conn()
    monkeypatch.setattr(offsec_pentest, "get_record_details_internal", lambda record_id: {"id": record_id})
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {"record_id": record_id, "tested_by": "alice", "status": "In Progress"},
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "owner")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: [])
    monkeypatch.setattr(offsec_pentest, "get_pentest_users_internal", lambda: [{"id": 1, "username": "bob"}])
    monkeypatch.setattr(offsec_pentest, "get_db_connection", lambda _: conn)

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "alice", "pentester")

    response = client.post("/pentest/8/collaborators", json={"username": "bob"})

    assert response.status_code == 200
    assert conn.committed is True
    assert any("insert into pentest_collaborators" in query for query, _ in conn.cursor_obj.executed)


def test_owner_cannot_remove_collaborator(monkeypatch):
    _allow_permissions(monkeypatch)
    monkeypatch.setattr(offsec_pentest, "get_record_details_internal", lambda record_id: {"id": record_id})
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {"record_id": record_id, "tested_by": "alice", "status": "In Progress"},
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "owner")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: ["bob"])

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "alice", "pentester")

    response = client.delete("/pentest/8/collaborators/bob")

    assert response.status_code == 403


def test_collaborator_can_leave(monkeypatch):
    _allow_permissions(monkeypatch)
    conn = _Conn()
    monkeypatch.setattr(offsec_pentest, "get_record_details_internal", lambda record_id: {"id": record_id})
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {"record_id": record_id, "tested_by": "alice", "status": "In Progress"},
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "collaborator")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: ["bob"])
    monkeypatch.setattr(offsec_pentest, "get_db_connection", lambda _: conn)

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "bob", "pentester")

    response = client.delete("/pentest/8/collaborators/bob")

    assert response.status_code == 200
    assert response.get_json()["message"] == "You left this pentest collaboration."
    assert conn.committed is True


def test_manager_cannot_add_collaborator_to_completed_test(monkeypatch):
    _allow_permissions(monkeypatch)
    monkeypatch.setattr(offsec_pentest, "get_record_details_internal", lambda record_id: {"id": record_id})
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {"record_id": record_id, "tested_by": "alice", "status": "Completed"},
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "manager_override")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: [])
    monkeypatch.setattr(offsec_pentest, "get_pentest_users_internal", lambda: [{"id": 1, "username": "bob"}])

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "manager1", "manager")

    response = client.post("/pentest/8/collaborators", json={"username": "bob"})

    assert response.status_code == 403


def test_collaborator_can_update_security_details(monkeypatch):
    _allow_permissions(monkeypatch)
    captured = {}
    conn = _Conn()
    monkeypatch.setattr(
        offsec_pentest,
        "get_record_details_internal",
        lambda record_id: {"id": record_id, "name": "host", "ip_address": "1.1.1.1", "source": "src", "description": "old"},
    )
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {
            "record_id": record_id,
            "tested_by": "alice",
            "status": "In Progress",
            "notes": "old-notes",
            "open_ports": "443",
            "vulnerabilities": "[]",
        },
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "collaborator")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: ["bob"])
    monkeypatch.setattr(offsec_pentest, "cleanup_unreferenced_images", lambda filenames: None)
    monkeypatch.setattr(offsec_pentest, "get_db_connection", lambda _: conn)
    monkeypatch.setattr(
        offsec_pentest,
        "_upsert_pentest_data",
        lambda cursor, pentest_data, existing_data: captured.setdefault("pentest_data", pentest_data),
    )

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "bob", "pentester")

    response = client.post(
        "/pentest/12",
        data={
            "tested_by": "alice",
            "description": "new description",
            "notes": "new notes",
            "open_ports": "443,8443",
        },
    )

    assert response.status_code == 200
    assert captured["pentest_data"]["notes"] == "new notes"
    assert captured["pentest_data"]["open_ports"] == "443,8443"
    assert any("update records set description" in query for query, _ in conn.cursor_obj.executed)


def test_collaborator_cannot_change_status(monkeypatch):
    _allow_permissions(monkeypatch)
    monkeypatch.setattr(
        offsec_pentest,
        "get_record_details_internal",
        lambda record_id: {"id": record_id, "name": "host", "ip_address": "1.1.1.1", "source": "src", "description": "old"},
    )
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {"record_id": record_id, "tested_by": "alice", "status": "In Progress", "vulnerabilities": "[]"},
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "collaborator")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: ["bob"])
    monkeypatch.setattr(offsec_pentest, "cleanup_unreferenced_images", lambda filenames: None)

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "bob", "pentester")

    response = client.post("/pentest/12", data={"status": "Completed"})

    assert response.status_code == 403


def test_collaborator_can_create_new_finding_with_ownership(monkeypatch):
    _allow_permissions(monkeypatch)
    captured = {}
    conn = _Conn()
    existing_finding = {
        "id": "finding-1",
        "description": "existing",
        "created_by": "alice",
        "created_at": "2026-04-14T00:00:00+00:00",
    }
    monkeypatch.setattr(
        offsec_pentest,
        "get_record_details_internal",
        lambda record_id: {"id": record_id, "name": "host", "ip_address": "1.1.1.1", "source": "src", "description": "old"},
    )
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {
            "record_id": record_id,
            "tested_by": "alice",
            "status": "In Progress",
            "notes": "",
            "open_ports": "",
            "vulnerabilities": json.dumps([existing_finding]),
        },
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "collaborator")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: ["bob"])
    monkeypatch.setattr(offsec_pentest, "cleanup_unreferenced_images", lambda filenames: None)
    monkeypatch.setattr(offsec_pentest, "get_db_connection", lambda _: conn)
    monkeypatch.setattr(
        offsec_pentest,
        "_upsert_pentest_data",
        lambda cursor, pentest_data, existing_data: captured.setdefault("pentest_data", pentest_data),
    )

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "bob", "pentester")

    response = client.post(
        "/pentest/12",
        data={
            "vulnerabilities": json.dumps(
                [
                    existing_finding,
                    {"id": "finding-2", "description": "new finding"},
                ]
            )
        },
    )

    findings = json.loads(captured["pentest_data"]["vulnerabilities"])
    created = next(item for item in findings if item["id"] == "finding-2")

    assert response.status_code == 200
    assert created["created_by"] == "bob"
    assert created["updated_by"] == "bob"


def test_collaborator_cannot_edit_or_delete_other_users_finding(monkeypatch):
    _allow_permissions(monkeypatch)
    existing_finding = {
        "id": "finding-1",
        "description": "existing",
        "created_by": "alice",
        "created_at": "2026-04-14T00:00:00+00:00",
    }
    monkeypatch.setattr(
        offsec_pentest,
        "get_record_details_internal",
        lambda record_id: {"id": record_id, "name": "host", "ip_address": "1.1.1.1", "source": "src", "description": "old"},
    )
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {
            "record_id": record_id,
            "tested_by": "alice",
            "status": "In Progress",
            "notes": "",
            "open_ports": "",
            "vulnerabilities": json.dumps([existing_finding]),
        },
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "collaborator")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: ["bob"])
    monkeypatch.setattr(offsec_pentest, "cleanup_unreferenced_images", lambda filenames: None)

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "bob", "pentester")

    edit_response = client.post(
        "/pentest/12",
        data={"vulnerabilities": json.dumps([{"id": "finding-1", "description": "changed"}])},
    )
    delete_response = client.post("/pentest/12", data={"vulnerabilities": "[]"})

    assert edit_response.status_code == 403
    assert delete_response.status_code == 403


def test_reassigning_to_existing_collaborator_swaps_membership(monkeypatch):
    _allow_permissions(monkeypatch)
    conn = _Conn()
    monkeypatch.setattr(
        offsec_pentest,
        "get_record_details_internal",
        lambda record_id: {"id": record_id, "name": "host", "ip_address": "1.1.1.1", "source": "src", "description": "old"},
    )
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {"record_id": record_id, "tested_by": "alice", "status": "In Progress", "vulnerabilities": "[]"},
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "manager_override")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: ["bob"])
    monkeypatch.setattr(
        offsec_pentest,
        "get_pentest_users_internal",
        lambda: [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}],
    )
    monkeypatch.setattr(offsec_pentest, "cleanup_unreferenced_images", lambda filenames: None)
    monkeypatch.setattr(offsec_pentest, "get_db_connection", lambda _: conn)
    monkeypatch.setattr(offsec_pentest, "_upsert_pentest_data", lambda cursor, pentest_data, existing_data: None)

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "manager1", "manager")

    response = client.post("/pentest/12", data={"tested_by": "bob"})

    assert response.status_code == 200
    assert any(
        query.startswith("delete from pentest_collaborators where record_id = ? and username = ?")
        and params == (12, "bob")
        for query, params in conn.cursor_obj.executed
    )
    assert any(
        "insert into pentest_collaborators" in query and params[0] == 12 and params[1] == "alice"
        for query, params in conn.cursor_obj.executed
    )


def test_reassigning_to_non_collaborator_does_not_swap_membership(monkeypatch):
    _allow_permissions(monkeypatch)
    conn = _Conn()
    monkeypatch.setattr(
        offsec_pentest,
        "get_record_details_internal",
        lambda record_id: {"id": record_id, "name": "host", "ip_address": "1.1.1.1", "source": "src", "description": "old"},
    )
    monkeypatch.setattr(
        offsec_pentest,
        "_load_existing_pentest_data",
        lambda record_id: {"record_id": record_id, "tested_by": "alice", "status": "In Progress", "vulnerabilities": "[]"},
    )
    monkeypatch.setattr(offsec_pentest, "get_access_role_for_user", lambda *args, **kwargs: "manager_override")
    monkeypatch.setattr(offsec_pentest, "get_collaborator_usernames", lambda record_id: ["carol"])
    monkeypatch.setattr(
        offsec_pentest,
        "get_pentest_users_internal",
        lambda: [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}, {"id": 3, "username": "carol"}],
    )
    monkeypatch.setattr(offsec_pentest, "cleanup_unreferenced_images", lambda filenames: None)
    monkeypatch.setattr(offsec_pentest, "get_db_connection", lambda _: conn)
    monkeypatch.setattr(offsec_pentest, "_upsert_pentest_data", lambda cursor, pentest_data, existing_data: None)

    app = _make_app()
    client = app.test_client()
    _set_logged_in_session(client, "manager1", "manager")

    response = client.post("/pentest/12", data={"tested_by": "bob"})

    assert response.status_code == 200
    assert not any(
        query.startswith("delete from pentest_collaborators where record_id = ? and username = ?")
        and params == (12, "bob")
        for query, params in conn.cursor_obj.executed
    )
    assert not any(
        "insert into pentest_collaborators" in query and params[0] == 12 and params[1] == "alice"
        for query, params in conn.cursor_obj.executed
    )
