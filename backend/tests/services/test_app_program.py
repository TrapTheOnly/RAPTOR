import importlib

from app.repositories.environments_repository import suggest_env_slug
from app.repositories.pentest_findings_repository import compute_global_status
from app.services import app_program_service


def test_resolve_merged_ticket_never_concatenates():
    from app.repositories.pentest_findings_repository import resolve_merged_ticket

    url_a = "https://jira.example.com/browse/SEC-1"
    url_b = "https://jira.example.com/browse/SEC-2"
    ticket, description = resolve_merged_ticket(url_a, url_b, "CORS on API")
    assert ticket == url_a
    assert "Also ticket: https://jira.example.com/browse/SEC-2" in description
    assert "; also" not in ticket

    ticket, description = resolve_merged_ticket("test; also asdsad", url_a, "")
    assert ticket == url_a
    assert description == ""

    ticket, description = resolve_merged_ticket(url_a, "not-a-url", "")
    assert ticket == url_a

    ticket, description = resolve_merged_ticket("junk", "also junk", "kept")
    assert ticket == "junk"
    assert description == "kept"


def test_merge_survivor_fields_fills_blanks_only():
    from app.repositories.pentest_findings_repository import merge_survivor_fields

    updates = merge_survivor_fields(
        {
            "title": "Keep me",
            "category_id": "",
            "category_name": "",
            "base_score": 0,
            "cvss_metrics": "{}",
            "auth_context": "",
        },
        {
            "title": "Drop me",
            "category_id": "12",
            "category_name": "SQL Injection",
            "base_score": 9.8,
            "cvss_metrics": '{"AV": "N"}',
            "auth_context": "user",
        },
    )
    assert "title" not in updates
    assert updates["category_name"] == "SQL Injection"
    assert updates["base_score"] == 9.8
    assert updates["auth_context"] == "user"

    scored = merge_survivor_fields(
        {"title": "Keep", "category_id": "1", "category_name": "XSS", "base_score": 7.5, "auth_context": "admin"},
        {"title": "Other", "category_id": "9", "category_name": "RCE", "base_score": 10, "auth_context": "user"},
    )
    assert scored == {}

    narrative = merge_survivor_fields(
        {"title": "Keep", "impact": "", "evidence": "Keep proof", "remediation": ""},
        {"title": "Other", "impact": "Account takeover", "evidence": "Drop me", "remediation": "Patch it"},
    )
    assert narrative["impact"] == "Account takeover"
    assert "evidence" not in narrative
    assert narrative["remediation"] == "Patch it"


def test_suggest_env_slug_markers():
    assert suggest_env_slug("api-stg.google.com") == "stg"
    assert suggest_env_slug("api-qa.google.com") == "qa"
    assert suggest_env_slug("api-pp.google.com") == "pp"
    assert suggest_env_slug("www.google.com") == ""
    assert suggest_env_slug("api.google.com") == ""


def test_compute_global_status_open_until_all_closed():
    assert compute_global_status(["fixed", "open"]) == "open"
    assert compute_global_status(["fixed", "not_affected"]) == "fixed"
    assert compute_global_status(["draft", "draft"], "scanner") == "draft"


def test_in_scope_backfill_ignores_empty_not_started():
    module = importlib.import_module("app.bootstrap.migrations.0014_environments")
    sql = []

    class Cursor:
        def execute(self, query, params=None):
            sql.append(" ".join(str(query).split()))
            return self

        def fetchall(self):
            return []

        def fetchone(self):
            return None

    module._backfill_host_envs(Cursor())
    joined = "\n".join(sql)
    assert "In Progress" in joined
    assert "Completed" in joined
    assert "human" in joined
    assert "Not Started" in joined or "pentest_data" in joined.lower()


def test_replace_findings_keeps_multi_host_rows(monkeypatch):
    from app.repositories import pentest_findings_repository as repo

    monkeypatch.setattr(repo, "_has_occurrences_table", lambda _cursor: True)
    monkeypatch.setattr(repo, "_refresh_finding_status", lambda *_args, **_kwargs: None)
    state = {"deleted": [], "detached": []}

    class Cursor:
        def execute(self, query, params=None):
            normalized = " ".join(str(query).split()).lower()
            self._normalized = normalized
            self._params = params
            if "from finding_occurrences" in normalized and "record_id <>" in normalized:
                self._rows = [{"record_id": 2}]
            elif normalized.startswith("delete from finding_occurrences") and params and len(params) == 2:
                state["detached"].append(params)
                self._rows = []
            elif normalized.startswith("delete from pentest_findings"):
                state["deleted"].append(params)
                self._rows = []
            else:
                self._rows = []
            return self

        def fetchall(self):
            return getattr(self, "_rows", [])

        def fetchone(self):
            rows = getattr(self, "_rows", [])
            return rows[0] if rows else None

    repo._detach_or_delete(Cursor(), "f1", 1)
    assert state["deleted"] == []
    assert state["detached"] == [("f1", 1)]


def test_environments_table_enforces_unique_app_slug(monkeypatch):
    module = importlib.import_module("app.bootstrap.migrations.0014_environments")
    monkeypatch.setattr(module, "get_table_columns", lambda *_args, **_kwargs: [])
    sql = []

    class Cursor:
        def execute(self, query, params=None):
            sql.append(" ".join(str(query).split()))
            return self

        def fetchall(self):
            return []

        def fetchone(self):
            return None

    module.up(Cursor())
    joined = "\n".join(sql)
    assert "UNIQUE (application_id, slug)" in joined
    assert "environment_id" in joined
    assert "in_scope" in joined


def test_delete_application_blocked_when_in_scope(monkeypatch):
    from app.repositories import applications_repository as apps

    class Cursor:
        def __init__(self):
            self.step = 0

        def execute(self, query, params=None):
            self.query = " ".join(str(query).split()).lower()
            return self

        def fetchone(self):
            if "from applications" in self.query:
                return {"id": 1}
            if "from records" in self.query:
                return {"n": 2}
            return {"n": 0}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

        def commit(self):
            raise AssertionError("must not commit a blocked delete")

    monkeypatch.setattr(apps, "get_db_connection", lambda _path: Conn())
    monkeypatch.setattr(apps, "get_table_columns", lambda *_args, **_kwargs: ["in_scope", "environment_id"])
    assert apps.delete_application(1) == "in_use"


def _env_conn(cursor):
    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return cursor

        def commit(self):
            cursor.committed = True

    return Conn()


def test_delete_environment_allows_unused_seeded_slug(monkeypatch):
    from app.repositories import environments_repository as repo

    class Cursor:
        committed = False

        def execute(self, query, params=None):
            self.query = " ".join(str(query).split()).lower()
            self.params = params
            return self

        def fetchone(self):
            if "select id, slug" in self.query:
                return {"id": 3, "slug": "stg"}
            return {"n": 0}

    cursor = Cursor()
    monkeypatch.setattr(repo, "get_db_connection", lambda _path: _env_conn(cursor))
    monkeypatch.setattr(repo, "get_table_columns", lambda *_args, **_kwargs: ["in_scope"])
    assert repo.delete_environment(1, 3) == "ok"
    assert cursor.committed is True


def test_delete_environment_protects_unassigned(monkeypatch):
    from app.repositories import environments_repository as repo

    class Cursor:
        committed = False

        def execute(self, query, params=None):
            self.query = " ".join(str(query).split()).lower()
            return self

        def fetchone(self):
            return {"id": 1, "slug": "unassigned"}

        def commit(self):
            raise AssertionError("must not delete unassigned")

    cursor = Cursor()
    monkeypatch.setattr(repo, "get_db_connection", lambda _path: _env_conn(cursor))
    assert repo.delete_environment(1, 1) == "protected"
    assert cursor.committed is False


def test_seed_environments_skips_when_catalog_exists(monkeypatch):
    from app.repositories import environments_repository as repo

    inserts = []

    class Cursor:
        def execute(self, query, params=None):
            normalized = " ".join(str(query).split()).lower()
            if "insert into environments" in normalized:
                inserts.append(params)
            self.query = normalized
            return self

        def fetchone(self):
            return {"n": 4}

    repo.seed_environments_for_app(Cursor(), 9)
    assert inserts == []


def test_assign_hosts_writes_application_id_cache(monkeypatch):
    from app.repositories import applications_repository as apps

    executed = []

    class Cursor:
        rowcount = 3

        def execute(self, query, params=None):
            executed.append((" ".join(str(query).split()).lower(), params))
            return self

        def fetchone(self):
            return {"id": 9}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

        def commit(self):
            return None

    monkeypatch.setattr(apps, "get_db_connection", lambda _path: Conn())
    updated = apps.assign_hosts(4, [1, 2, 3], 9, True)
    assert updated == 3
    update_sql = executed[-1][0]
    assert "application_id = ?" in update_sql
    assert executed[-1][1][:2] == (9, 4)


def test_fetch_app_findings_accepts_host_snapshot_filter():
    import inspect
    from app.repositories.pentest_findings_repository import fetch_app_findings, detach_findings_for_record

    assert "record_ids" in inspect.signature(fetch_app_findings).parameters
    assert "wave_id" in inspect.signature(fetch_app_findings).parameters
    assert callable(detach_findings_for_record)


def test_get_finding_404(monkeypatch):
    monkeypatch.setattr(
        "app.repositories.pentest_findings_repository.get_finding",
        lambda *_a, **_k: None,
    )
    payload, status = app_program_service.get_finding("missing")
    assert status == 404
    assert "error" in payload


def test_closed_wave_rejects_finding_mutations(monkeypatch):
    finding = {"id": "f1", "discovered_wave_id": 4, "title": "CORS"}
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "get_finding",
        lambda *_a, **_k: finding,
    )
    monkeypatch.setattr(
        app_program_service.phase2b_repository,
        "get_wave",
        lambda *_a, **_k: {"id": 4, "application_id": 1, "status": "closed"},
    )
    patched, status = app_program_service.patch_finding("f1", {"title": "nope"})
    assert status == 400
    assert "ended" in patched["error"].lower()
    occ, occ_status = app_program_service.patch_occurrence("f1", 11, {"status": "fixed"})
    assert occ_status == 400
    extra, extra_status = app_program_service.add_occurrences("f1", {"record_ids": [12]})
    assert extra_status == 400
    promoted, promote_status = app_program_service.promote_finding("f1", {})
    assert promote_status == 400
    merged, merge_status = app_program_service.merge_findings("f1", {"loser_id": "f2"})
    assert merge_status == 400
    deleted, delete_status = app_program_service.delete_finding("f1", username="ada", role="pentester")
    assert delete_status == 400
    assert "ended" in deleted["error"].lower()


def test_create_finding_rejects_closed_wave(monkeypatch):
    monkeypatch.setattr(
        app_program_service.applications_repository,
        "fetch_application",
        lambda *_a, **_k: {"id": 1},
    )
    monkeypatch.setattr(
        app_program_service,
        "fetch_record_by_id",
        lambda *_a, **_k: {"id": 11, "application_id": 1, "environment_id": 9},
    )
    monkeypatch.setattr(app_program_service, "_host_access_error", lambda *_a, **_k: None)
    monkeypatch.setattr(
        app_program_service.phase2b_repository,
        "get_wave",
        lambda *_a, **_k: {"id": 4, "application_id": 1, "status": "closed"},
    )
    payload, status = app_program_service.create_finding(
        1, {"record_id": 11, "wave_id": 4, "title": "CORS"}, "alice"
    )
    assert status == 400
    assert "ended" in payload["error"].lower()


def test_patch_finding_allows_unassigned_finding(monkeypatch):
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "get_finding",
        lambda *_a, **_k: {"id": "f1", "discovered_wave_id": None},
    )
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "update_finding_fields",
        lambda *_a, **_k: {"id": "f1", "title": "kept"},
    )
    payload, status = app_program_service.patch_finding("f1", {"title": "kept"})
    assert status == 200
    assert payload["finding"]["title"] == "kept"


def test_create_finding_allows_unassigned_tester_when_env_open(monkeypatch):
    monkeypatch.setattr(
        app_program_service.applications_repository,
        "fetch_application",
        lambda *_a, **_k: {"id": 1},
    )
    monkeypatch.setattr(
        app_program_service,
        "fetch_record_by_id",
        lambda *_a, **_k: {"id": 11, "application_id": 1, "environment_id": 9},
    )
    monkeypatch.setattr(
        app_program_service,
        "enforce_pentest_record_access",
        lambda *_a, **_k: (False, "You are not allowed to create a finding on this pentest."),
    )
    monkeypatch.setattr(app_program_service, "_acl_env_ids", lambda *_a, **_k: None)
    monkeypatch.setattr(app_program_service.phase2b_repository, "find_open_wave_for_env", lambda *_a, **_k: None)
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "insert_finding",
        lambda *_a, **_k: "f-new",
    )
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "replace_finding_collaborators",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "get_finding",
        lambda *_a, **_k: {"id": "f-new", "title": "CORS"},
    )
    payload, status = app_program_service.create_finding(
        1, {"record_id": 11, "title": "CORS"}, "alice", role="pentester"
    )
    assert status == 201
    assert payload["finding"]["id"] == "f-new"


def test_create_finding_denies_assigned_tester_outside_acl(monkeypatch):
    monkeypatch.setattr(
        app_program_service.applications_repository,
        "fetch_application",
        lambda *_a, **_k: {"id": 1},
    )
    monkeypatch.setattr(
        app_program_service,
        "fetch_record_by_id",
        lambda *_a, **_k: {"id": 11, "application_id": 1, "environment_id": 9},
    )
    monkeypatch.setattr(
        app_program_service,
        "enforce_pentest_record_access",
        lambda *_a, **_k: (True, None),
    )
    monkeypatch.setattr(app_program_service, "_acl_env_ids", lambda *_a, **_k: [10])
    payload, status = app_program_service.create_finding(
        1, {"record_id": 11, "title": "CORS"}, "alice", role="pentester"
    )
    assert status == 403
    assert "not visible" in payload["error"]


def test_get_finding_allows_unassigned_when_env_open(monkeypatch):
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "get_finding",
        lambda *_a, **_k: {"id": "f1", "record_id": 11, "application_id": 1},
    )
    monkeypatch.setattr(
        app_program_service,
        "fetch_record_by_id",
        lambda *_a, **_k: {"id": 11, "application_id": 1, "environment_id": 9, "name": "api.example"},
    )
    monkeypatch.setattr(app_program_service, "_acl_env_ids", lambda *_a, **_k: None)
    monkeypatch.setattr(
        app_program_service.environments_repository,
        "fetch_environment",
        lambda *_a, **_k: {"id": 9, "slug": "prod"},
    )
    payload, status = app_program_service.get_finding("f1", username="alice", role="pentester")
    assert status == 200
    assert payload["finding"]["id"] == "f1"


def test_get_finding_denies_when_env_hidden(monkeypatch):
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "get_finding",
        lambda *_a, **_k: {"id": "f1", "record_id": 11},
    )
    monkeypatch.setattr(
        app_program_service,
        "fetch_record_by_id",
        lambda *_a, **_k: {"id": 11, "application_id": 1, "environment_id": 9},
    )
    monkeypatch.setattr(app_program_service, "_acl_env_ids", lambda *_a, **_k: [10])
    payload, status = app_program_service.get_finding("f1", username="alice", role="pentester")
    assert status == 403
    assert "not visible" in payload["error"]


def test_assign_tester_self_claim_allowed(monkeypatch):
    monkeypatch.setattr(
        app_program_service.applications_repository,
        "fetch_application",
        lambda *_a, **_k: {"id": 1},
    )

    class Cursor:
        def execute(self, query, params=None):
            return self

        def fetchall(self):
            return [{"id": 11}]

    class Conn:
        row_factory = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(
        "app.integrations.db.connection.get_db_connection",
        lambda _path: Conn(),
    )
    monkeypatch.setattr(app_program_service, "_acl_env_ids", lambda *_a, **_k: None)
    monkeypatch.setattr(app_program_service, "fetch_record_by_id", lambda *_a, **_k: {"id": 11, "environment_id": 9})
    monkeypatch.setattr(
        app_program_service.phase2b_repository,
        "assign_record_testers",
        lambda *_a, **_k: 1,
    )
    monkeypatch.setattr(app_program_service.phase2b_repository, "fetch_host_env", lambda *_a, **_k: None)
    payload, status = app_program_service.assign_host_testers(
        1,
        {"record_ids": [11], "username": "Alice"},
        username="alice",
        role="pentester",
    )
    assert status == 200
    assert payload["tested_by"] == "Alice"


def test_assign_tester_other_user_requires_reassign_permission(monkeypatch):
    monkeypatch.setattr(
        app_program_service,
        "user_has_permission",
        lambda username, role, permission: False,
    )
    payload, status = app_program_service.assign_host_testers(
        1,
        {"record_ids": [11], "username": "bob"},
        username="alice",
        role="pentester",
    )
    assert status == 403
    assert "reassign_pentests_admin" in payload["error"]


def test_search_hosts_drops_hidden_envs_keeps_unfiled(monkeypatch):
    rows = [
        {"id": 1, "name": "open.example.com", "application_id": 1, "environment_id": 9},
        {"id": 2, "name": "hidden.example.com", "application_id": 1, "environment_id": 10},
        {"id": 3, "name": "unfiled.example.com", "application_id": None, "environment_id": None},
    ]

    class Cursor:
        def execute(self, query, params=None):
            return self

        def fetchall(self):
            return rows

    class Conn:
        row_factory = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr("app.integrations.db.connection.get_db_connection", lambda _path: Conn())
    monkeypatch.setattr(app_program_service, "_acl_env_ids", lambda app_id, username, role: [9])
    payload, status = app_program_service.search_hosts(
        {"q": "example"}, username="alice", role="pentester"
    )
    assert status == 200
    ids = [host["id"] for host in payload["hosts"]]
    assert ids == [1, 3]


def test_get_applications_redacts_sensitive_fields_and_filters_envs(monkeypatch):
    from flask import Flask

    from app.services import records_service

    apps = [
        {
            "id": 1,
            "name": "Google",
            "roe_link": "https://secret",
            "idp": "okta",
            "token_audience": "aud",
            "cookie_domain": ".google.com",
            "app_lead": "lead1",
            "host_count": 12,
            "in_scope_count": 8,
            "environments": [
                {"id": 9, "slug": "prod", "in_scope_count": 5},
                {"id": 10, "slug": "stg", "in_scope_count": 3},
            ],
        }
    ]
    monkeypatch.setattr(records_service.applications_repository, "fetch_applications", lambda: apps)
    monkeypatch.setattr(
        "app.services.phase2b_service.visible_env_ids",
        lambda *_a, **_k: [9],
    )
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret"

    @flask_app.route("/apps")
    def _apps():
        payload, status = records_service.get_applications()
        return {"payload": payload, "status": status}

    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["username"] = "contractor"
        sess["user_type"] = "pentester"
    response = client.get("/apps")
    body = response.get_json()
    assert body["status"] == 200
    app = body["payload"][0]
    assert app["host_count"] == 12
    assert [env["id"] for env in app["environments"]] == [9]
    assert "roe_link" not in app
    assert "idp" not in app
    assert "token_audience" not in app


def test_delete_finding_allows_reporter(monkeypatch):
    monkeypatch.setattr(app_program_service, "user_has_permission", lambda *_a, **_k: False)
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "get_finding",
        lambda *_a, **_k: {"id": "f1", "created_by": "ada", "collaborators": [], "source": "human"},
    )
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "delete_finding",
        lambda finding_id: {"id": finding_id},
    )
    payload, status = app_program_service.delete_finding("f1", username="ada", role="pentester")
    assert status == 200
    assert payload["deleted"] is True


def test_delete_finding_rejects_unrelated_tester(monkeypatch):
    monkeypatch.setattr(app_program_service, "user_has_permission", lambda *_a, **_k: False)
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "get_finding",
        lambda *_a, **_k: {"id": "f1", "created_by": "bob", "collaborators": [], "source": "human"},
    )
    payload, status = app_program_service.delete_finding("f1", username="ada", role="pentester")
    assert status == 403
    assert "reporter" in payload["error"].lower()


def test_delete_finding_allows_scanner_source_for_testers(monkeypatch):
    monkeypatch.setattr(app_program_service, "user_has_permission", lambda *_a, **_k: False)
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "get_finding",
        lambda *_a, **_k: {
            "id": "f1",
            "created_by": "RAPTOR-Scanner",
            "collaborators": [],
            "source": "scanner",
        },
    )
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "delete_finding",
        lambda finding_id: {"id": finding_id},
    )
    payload, status = app_program_service.delete_finding("f1", username="ada", role="pentester")
    assert status == 200
    assert payload["id"] == "f1"
