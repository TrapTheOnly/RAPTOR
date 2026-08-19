from app.repositories import pentest_findings_repository as findings_repo
from app.repositories import phase2b_repository
from app.services import app_program_service
from app.services import app_report_service as report_svc
from app.services import phase2b_service as svc
from app.services import scanner_service


def test_package_defaults():
    assert svc.package_defaults("owner_delivery")["prod_default"] is True
    assert svc.package_defaults("internal_draft")["include_drafts"] is True
    assert svc.package_defaults("retest_pack")["occurrence_statuses"] == ["open", "retest"]
    assert svc.package_defaults("nope")["package"] == "owner_delivery"


def test_hmac_signature_roundtrip(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    signature = svc.sign_export("abc123")
    assert svc.verify_signature("abc123", signature)
    assert not svc.verify_signature("abc123", "deadbeef")


def test_merge_checklist_keys_appends():
    merged = svc.merge_checklist_keys('{"selected": ["owasp-web"], "statuses": {}}', ["api", "owasp-web"])
    assert '"api"' in merged
    assert merged.count("owasp-web") == 1


def test_visible_env_ids_override_and_lead(monkeypatch):
    monkeypatch.setattr(
        svc.applications_repository,
        "fetch_application",
        lambda _id: {"app_lead": "lead1"},
    )
    captured = {}

    def fake_allowed(_app_id, username, *, is_override, app_lead="", db_path=None):
        captured["is_override"] = is_override
        captured["app_lead"] = app_lead
        captured["username"] = username
        if is_override or username == app_lead:
            return None
        return [9]

    monkeypatch.setattr(svc.phase2b_repository, "allowed_environment_ids", fake_allowed)
    assert svc.visible_env_ids(1, "admin1", "admin") is None
    assert captured["is_override"] is True
    assert svc.visible_env_ids(1, "lead1", "pentester") is None
    assert svc.visible_env_ids(1, "contractor", "pentester") == [9]


def test_wave_archive_requires_wave_id(monkeypatch):
    monkeypatch.setattr(
        report_svc.applications_repository,
        "fetch_application",
        lambda _id: {"id": 1, "name": "Google"},
    )
    payload, status = report_svc.generate_scoped_report(
        scope_kind="application",
        scope_id=1,
        data={"package": "wave_archive"},
        username="alice",
    )
    assert status == 400
    assert "wave_id" in payload["error"]


def test_retest_pack_keeps_open_like_occurrences(monkeypatch):
    findings = [
        {
            "id": "f1",
            "status": "open",
            "baseScore": 9.8,
            "title": "CORS",
            "occurrences": [
                {"record_id": 1, "dns_name": "www.google.com", "environment_slug": "prod", "status": "fixed"},
                {"record_id": 2, "dns_name": "stg.google.com", "environment_slug": "stg", "status": "open"},
            ],
        }
    ]
    monkeypatch.setattr(
        report_svc.pentest_findings_repository,
        "fetch_app_findings",
        lambda *args, **kwargs: (findings, 1),
    )
    monkeypatch.setattr(
        report_svc,
        "_split_occurrences",
        lambda occurrences, _ids: {"primary": list(occurrences), "observed": []},
    )
    packed, _drafts, _unassigned = report_svc._pack_findings(
        1,
        [10],
        include_drafts=False,
        occurrence_statuses=["open", "retest"],
    )
    assert packed[0]["occurrences"] == [
        {"record_id": 2, "dns_name": "stg.google.com", "environment_slug": "stg", "status": "open"}
    ]


def test_internal_draft_includes_drafts(monkeypatch):
    findings = [
        {
            "id": "draft",
            "status": "draft",
            "baseScore": 9.1,
            "title": "Draft XSS",
            "occurrences": [
                {"record_id": 1, "dns_name": "www.google.com", "environment_slug": "prod", "status": "draft"},
            ],
        }
    ]
    monkeypatch.setattr(
        report_svc.pentest_findings_repository,
        "fetch_app_findings",
        lambda *args, **kwargs: (findings, 1),
    )
    monkeypatch.setattr(
        report_svc,
        "_split_occurrences",
        lambda occurrences, _ids: {"primary": list(occurrences), "observed": []},
    )
    packed, excluded, _unassigned = report_svc._pack_findings(1, [10], include_drafts=True)
    assert excluded == 1
    assert packed[0]["id"] == "draft"


def test_generate_persists_hmac_signature(monkeypatch):
    inserts = []

    class Cursor:
        def execute(self, query, params=None):
            normalized = " ".join(str(query).split()).lower()
            if "from report_templates" in normalized:
                self._row = {
                    "id": 3,
                    "key": "default",
                    "name": "Default",
                    "description": "",
                    "template_json": "{}",
                    "enabled": 1,
                }
            elif normalized.startswith("insert into report_exports"):
                inserts.append(params)
                self._row = {"id": 44}
            else:
                self._row = None
            return self

        def fetchone(self):
            return self._row

    class Conn:
        row_factory = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

        def commit(self):
            return None

    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setattr(report_svc, "get_db_connection", lambda _path: Conn())
    monkeypatch.setattr(
        report_svc.applications_repository,
        "fetch_application",
        lambda _id: {"id": 1, "name": "Google", "roe_link": ""},
    )
    monkeypatch.setattr(
        report_svc,
        "_default_env_ids",
        lambda _app_id, _requested: ([9], [{"id": 9, "slug": "prod", "is_production": True}]),
    )
    monkeypatch.setattr(
        report_svc,
        "_pack_findings",
        lambda *args, **kwargs: ([{"id": "f1", "title": "CORS", "occurrences": [], "also_observed": []}], 0, []),
    )
    monkeypatch.setattr(report_svc, "safe_json_load", lambda *_args, **_kwargs: {"blocks": []})
    monkeypatch.setattr(report_svc, "bind_report_template_logo_for_template", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(report_svc, "render_pentest_report_pdf", lambda *_args, **_kwargs: b"%PDF")
    monkeypatch.setattr(report_svc, "load_enabled_checklist_templates", lambda: [])
    monkeypatch.setattr(report_svc, "save_report", lambda *_args, **_kwargs: "reports/app-1.pdf")

    payload, status = report_svc.generate_scoped_report(
        scope_kind="application",
        scope_id=1,
        data={"package": "retest_pack", "selected_env_ids": [9]},
        username="alice",
    )
    assert status == 200
    assert payload["package"] == "retest_pack"
    assert payload["signature"]
    assert inserts[0][9] == "retest_pack"
    assert svc.verify_signature(inserts[0][8], inserts[0][10])


def test_share_rejects_same_app(monkeypatch):
    monkeypatch.setattr(svc.applications_repository, "fetch_application", lambda _id: {"id": 1})
    payload, status = svc.share_host(1, 10, {"consumer_application_id": 1})
    assert status == 400


def test_host_visible_to_app_shared(monkeypatch):
    monkeypatch.setattr(phase2b_repository, "_table_exists", lambda _cursor, _name: True)

    class Cursor:
        def __init__(self):
            self.query = ""

        def execute(self, query, params=None):
            self.query = query
            self.params = params
            return self

        def fetchone(self):
            if "FROM records" in self.query:
                return None
            if "shared_host_apps" in self.query:
                return (1,)
            return None

    assert phase2b_repository.host_visible_to_app(Cursor(), 10, 2) is True


def test_retest_is_a_valid_occurrence_status():
    assert "retest" in findings_repo.OCCURRENCE_STATUSES
    assert findings_repo.OCCURRENCE_STATUSES >= {"open", "retest", "fixed", "not_affected", "accepted"}


def test_patch_occurrence_rejects_unknown_status(monkeypatch):
    def boom(*_args, **_kwargs):
        raise ValueError("invalid_occurrence_status")

    monkeypatch.setattr(app_program_service.pentest_findings_repository, "set_occurrence_status", boom)
    payload, status = app_program_service.patch_occurrence("f1", 5, {"status": "banana"})
    assert status == 400
    assert "retest" in payload["error"]


def test_patch_occurrence_requires_status():
    payload, status = app_program_service.patch_occurrence("f1", 5, {})
    assert status == 400


def test_patch_occurrence_404_when_missing(monkeypatch):
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository,
        "set_occurrence_status",
        lambda *_args, **_kwargs: None,
    )
    payload, status = app_program_service.patch_occurrence("f1", 5, {"status": "retest"})
    assert status == 404


def test_set_occurrence_status_refreshes_rollups(monkeypatch):
    calls = {"rollup": [], "finding": [], "updates": []}

    class Cursor:
        rowcount = 1

        def execute(self, query, params=None):
            normalized = " ".join(str(query).split()).lower()
            if normalized.startswith("update finding_occurrences"):
                calls["updates"].append(params)
            return self

        def fetchone(self):
            return None

        def fetchall(self):
            return []

    class Conn:
        row_factory = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

        def commit(self):
            calls["committed"] = True

    monkeypatch.setattr(findings_repo, "get_db_connection", lambda _path: Conn())
    monkeypatch.setattr(findings_repo, "_has_occurrences_table", lambda _cursor: True)
    monkeypatch.setattr(findings_repo, "_refresh_host_rollup", lambda _c, rid: calls["rollup"].append(rid))
    monkeypatch.setattr(findings_repo, "_refresh_finding_status", lambda _c, fid: calls["finding"].append(fid))
    monkeypatch.setattr(findings_repo, "get_finding", lambda fid, db_path=None: {"id": fid})

    result = findings_repo.set_occurrence_status("f1", 7, "retest")
    assert result == {"id": "f1"}
    assert calls["updates"] == [("retest", "f1", 7)]
    assert calls["rollup"] == [7]
    assert calls["finding"] == ["f1"]


def test_bulk_set_occurrence_status_scopes_by_env(monkeypatch):
    state = {"updates": [], "refreshed": []}

    class Cursor:
        def execute(self, query, params=None):
            normalized = " ".join(str(query).split()).lower()
            self._select = "select o.finding_id" in normalized
            if normalized.startswith("update finding_occurrences"):
                state["updates"].append(params)
            if self._select:
                state["where"] = normalized
                state["params"] = params
            return self

        def fetchall(self):
            if getattr(self, "_select", False):
                return [{"finding_id": "f1", "record_id": 3}, {"finding_id": "f1", "record_id": 4}]
            return []

        def fetchone(self):
            return None

    class Conn:
        row_factory = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

        def commit(self):
            return None

    monkeypatch.setattr(findings_repo, "get_db_connection", lambda _path: Conn())
    monkeypatch.setattr(findings_repo, "_has_occurrences_table", lambda _cursor: True)
    monkeypatch.setattr(findings_repo, "_refresh_host_rollup", lambda _c, _rid: None)
    monkeypatch.setattr(
        findings_repo, "_refresh_finding_status", lambda _c, fid: state["refreshed"].append(fid)
    )

    updated = findings_repo.bulk_set_occurrence_status(
        1, "retest", from_statuses=["open"], env_ids=[9]
    )
    assert updated == 2
    assert state["updates"] == [("retest", "f1", 3), ("retest", "f1", 4)]
    assert state["refreshed"] == ["f1"]
    assert "r.environment_id in" in state["where"]
    assert 9 in state["params"]


def test_bulk_status_defaults_to_open_like(monkeypatch):
    captured = {}

    def fake_bulk(app_id, to_status, from_statuses=None, env_ids=None, record_ids=None):
        captured.update(
            {
                "app_id": app_id,
                "to_status": to_status,
                "from_statuses": from_statuses,
                "env_ids": env_ids,
                "record_ids": record_ids,
            }
        )
        return 3

    monkeypatch.setattr(app_program_service.applications_repository, "fetch_application", lambda _id: {"id": 1})
    monkeypatch.setattr(
        app_program_service.pentest_findings_repository, "bulk_set_occurrence_status", fake_bulk
    )
    payload, status = app_program_service.bulk_set_occurrence_status(1, {"env_ids": [9]})
    assert status == 200
    assert payload == {"updated": 3, "to_status": "retest"}
    assert captured["from_statuses"] is None
    assert captured["env_ids"] == [9]


def _scanner_ready(monkeypatch):
    monkeypatch.setattr(
        scanner_service,
        "get_scanner_config",
        lambda: {
            "enabled": 1,
            "bedrock_model_id": "model",
            "max_concurrent_scans": 4,
            "allow_destructive_tools": 1,
            "aws_region": "us-east-1",
        },
    )
    monkeypatch.setattr(scanner_service, "fetch_pentest_row", lambda _id: {"scan_status": "idle"})
    monkeypatch.setattr(scanner_service, "count_running_scans", lambda: 0)


def test_scanner_env_ceiling(monkeypatch):
    _scanner_ready(monkeypatch)
    monkeypatch.setattr(
        "app.repositories.phase2b_repository.fetch_host_env",
        lambda _id: {"id": 7, "allow_destructive": 1, "max_concurrent_scans": 1},
    )
    monkeypatch.setattr("app.repositories.phase2b_repository.count_running_scans_for_env", lambda _id: 1)
    payload, status = scanner_service.launch_scan_payload(3)
    assert status == 429
    assert "Environment scan ceiling" in payload["error"]


def test_scanner_destructive_requires_env_and_global(monkeypatch):
    _scanner_ready(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        "app.repositories.phase2b_repository.fetch_host_env",
        lambda _id: {"id": 7, "application_id": 1, "allow_destructive": 0, "max_concurrent_scans": 2},
    )
    monkeypatch.setattr("app.repositories.phase2b_repository.count_running_scans_for_env", lambda _id: 0)
    monkeypatch.setattr(
        "app.repositories.phase2b_repository.find_open_wave_for_env",
        lambda *_a, **_k: {"id": 4, "status": "open", "started_at": "2026-08-01"},
    )
    monkeypatch.setattr(
        scanner_service,
        "_dispatch_scan",
        lambda record_id, cfg, allow_destructive=None: captured.update({"allow": allow_destructive}),
    )
    payload, status = scanner_service.launch_scan_payload(3)
    assert status == 202
    assert captured["allow"] is False
    assert payload["record_id"] == 3


def test_get_wave_404_when_missing(monkeypatch):
    monkeypatch.setattr(svc.applications_repository, "fetch_application", lambda _id: {"id": 1})
    monkeypatch.setattr(svc.phase2b_repository, "get_wave", lambda _id: None)
    payload, status = svc.get_wave(1, 99)
    assert status == 404
    assert "error" in payload


def test_get_wave_empty_snapshot_has_no_findings(monkeypatch):
    monkeypatch.setattr(svc.applications_repository, "fetch_application", lambda _id: {"id": 1})
    monkeypatch.setattr(
        svc.phase2b_repository,
        "get_wave",
        lambda _id: {"id": 4, "application_id": 1, "name": "H1", "host_snapshot": [], "environment_id": 9, "env_ids": [9]},
    )
    monkeypatch.setattr(svc.environments_repository, "fetch_environment", lambda *_a, **_k: {"id": 9, "slug": "prod"})
    monkeypatch.setattr(svc.phase2b_repository, "list_live_wave_hosts", lambda *_a, **_k: [])
    monkeypatch.setattr(
        "app.repositories.pentest_findings_repository.fetch_app_findings",
        lambda *args, **kwargs: ([], 0),
    )
    payload, status = svc.get_wave(1, 4)
    assert status == 200
    assert payload["hosts"] == []
    assert payload["findings"] == []
    assert payload["finding_total"] == 0
    assert payload["environment"]["slug"] == "prod"
    assert payload["environments"][0]["slug"] == "prod"


def test_get_wave_findings_are_only_stamped_on_this_wave(monkeypatch):
    calls = []
    monkeypatch.setattr(svc.applications_repository, "fetch_application", lambda _id: {"id": 1})
    monkeypatch.setattr(
        svc.phase2b_repository,
        "get_wave",
        lambda _id: {"id": 4, "application_id": 1, "name": "H2", "env_ids": [9]},
    )
    monkeypatch.setattr(svc.environments_repository, "fetch_environment", lambda *_a, **_k: {"id": 9, "slug": "prod"})
    monkeypatch.setattr(
        svc.phase2b_repository,
        "list_live_wave_hosts",
        lambda *_a, **_k: [{"id": 11, "finding_count": 0}],
    )

    def fake_fetch(*_args, **kwargs):
        calls.append(kwargs)
        return ([{"id": "this-wave", "discovered_wave_id": 4}], 1)

    monkeypatch.setattr("app.repositories.pentest_findings_repository.fetch_app_findings", fake_fetch)
    payload, status = svc.get_wave(1, 4)
    assert status == 200
    assert payload["findings"] == [{"id": "this-wave", "discovered_wave_id": 4}]
    assert len(calls) == 1
    assert calls[0]["wave_id"] == 4
    assert "record_ids" not in calls[0]


def test_start_wave_marks_hosts_in_progress(monkeypatch):
    monkeypatch.setattr(
        svc.phase2b_repository,
        "get_wave",
        lambda _id: {"id": 4, "application_id": 1, "status": "open", "started_at": None},
    )
    monkeypatch.setattr(
        svc.phase2b_repository,
        "start_wave",
        lambda *_a, **_k: {"id": 4, "application_id": 1, "status": "open", "started_at": "2026-08-19"},
    )
    payload, status = svc.start_wave(1, 4)
    assert status == 200
    assert payload["wave"]["started_at"]


def test_start_wave_rejects_already_started(monkeypatch):
    monkeypatch.setattr(
        svc.phase2b_repository,
        "get_wave",
        lambda _id: {"id": 4, "application_id": 1, "status": "open", "started_at": "2026-08-01"},
    )
    payload, status = svc.start_wave(1, 4)
    assert status == 400
    assert "already started" in payload["error"].lower()


def test_create_wave_requires_one_environment(monkeypatch):
    monkeypatch.setattr(svc.applications_repository, "fetch_application", lambda _id: {"id": 1})
    payload, status = svc.create_wave(1, {"name": "H1"}, "alice")
    assert status == 400
    assert "environment" in payload["error"].lower()


def test_claim_wave_hosts_requires_membership(monkeypatch):
    monkeypatch.setattr(
        svc.phase2b_repository,
        "get_wave",
        lambda _id: {
            "id": 4,
            "application_id": 1,
            "opened_by": "alice",
            "members": ["alice", "bob"],
            "host_snapshot": [11, 12],
            "env_ids": [9],
            "status": "open",
        },
    )
    monkeypatch.setattr(
        svc.phase2b_repository,
        "list_live_wave_hosts",
        lambda *_a, **_k: [{"id": 11}, {"id": 12}],
    )
    payload, status = svc.claim_wave_hosts(1, 4, {"record_ids": [11]}, "eve")
    assert status == 403
    captured = {}
    monkeypatch.setattr(
        svc.phase2b_repository,
        "assign_record_testers",
        lambda ids, username: captured.update({"ids": ids, "username": username}) or len(ids),
    )
    monkeypatch.setattr(svc.phase2b_repository, "sync_wave_host_collaborators", lambda *_a, **_k: None)
    payload, status = svc.claim_wave_hosts(1, 4, {"record_ids": [11, 99]}, "bob")
    assert status == 200
    assert payload["tested_by"] == "bob"
    assert captured["ids"] == [11]


def test_create_wave_accepts_multiple_environments(monkeypatch):
    monkeypatch.setattr(svc.applications_repository, "fetch_application", lambda _id: {"id": 1})
    monkeypatch.setattr(
        svc.environments_repository,
        "fetch_environments",
        lambda _id: [{"id": 9}, {"id": 10}],
    )
    captured = {}
    monkeypatch.setattr(svc.phase2b_repository, "list_acl", lambda *_a, **_k: [])
    monkeypatch.setattr(
        svc.phase2b_repository,
        "create_wave",
        lambda app_id, name, env_ids, username, notes="", members=None: captured.update({"env_ids": list(env_ids)})
        or {"id": 1, "members": ["alice"]},
    )
    monkeypatch.setattr(svc.phase2b_repository, "sync_wave_host_collaborators", lambda *_a, **_k: None)
    monkeypatch.setattr(svc.phase2b_repository, "set_live_wave_host_status", lambda *_a, **_k: 0)
    payload, status = svc.create_wave(1, {"name": "H1", "env_ids": [9, 10]}, "alice")
    assert status == 201
    assert captured["env_ids"] == [9, 10]


def test_delete_wave_404_when_missing(monkeypatch):
    monkeypatch.setattr(svc.phase2b_repository, "get_wave", lambda _id: None)
    payload, status = svc.delete_wave(1, 99)
    assert status == 404
    assert "error" in payload


def test_wave_is_open_treats_closed_and_ended_as_frozen():
    assert svc.wave_is_open(None) is True
    assert svc.wave_is_open({"status": "open"}) is True
    assert svc.wave_is_open({"status": "closed"}) is False
    assert svc.wave_is_open({"status": "open", "closed_at": "2026-08-01"}) is False
    payload, status = svc.reject_if_closed({"status": "closed"})
    assert status == 400
    assert "ended" in payload["error"].lower()
    assert svc.reject_if_closed({"status": "open"}) is None


def _closed_wave():
    return {
        "id": 4,
        "application_id": 1,
        "status": "closed",
        "closed_at": "2026-08-19",
        "members": ["alice"],
        "env_ids": [9],
        "host_snapshot": [11],
    }


def test_closed_wave_rejects_member_and_env_and_scope_and_claim(monkeypatch):
    monkeypatch.setattr(svc.phase2b_repository, "get_wave", lambda _id: _closed_wave())
    members, member_status = svc.put_wave_members(1, 4, {"usernames": ["bob"]})
    assert member_status == 400
    assert "ended" in members["error"].lower()
    envs, env_status = svc.put_wave_environments(1, 4, {"env_ids": [9]})
    assert env_status == 400
    scope, scope_status = svc.set_wave_host_scope(1, 4, {"record_ids": [11], "in_scope": False})
    assert scope_status == 400
    claim, claim_status = svc.claim_wave_hosts(1, 4, {"record_ids": [11]}, "alice")
    assert claim_status == 400
    assert claim["error"] == svc.CLOSED_WAVE_ERROR


def test_closed_wave_still_allows_delete(monkeypatch):
    monkeypatch.setattr(svc.phase2b_repository, "get_wave", lambda _id: _closed_wave())
    monkeypatch.setattr(svc.phase2b_repository, "delete_wave", lambda *_a, **_k: True)
    payload, status = svc.delete_wave(1, 4)
    assert status == 200


def test_scanner_rejects_without_open_started_wave(monkeypatch):
    _scanner_ready(monkeypatch)
    monkeypatch.setattr(
        "app.repositories.phase2b_repository.fetch_host_env",
        lambda _id: {"id": 7, "application_id": 1, "allow_destructive": 1, "max_concurrent_scans": 2},
    )
    monkeypatch.setattr("app.repositories.phase2b_repository.count_running_scans_for_env", lambda _id: 0)
    monkeypatch.setattr(
        "app.repositories.phase2b_repository.find_open_wave_for_env",
        lambda *_a, **_k: {"id": 4, "status": "open", "started_at": None},
    )
    payload, status = scanner_service.launch_scan_payload(3)
    assert status == 400
    assert "start the wave" in payload["error"].lower()
    monkeypatch.setattr("app.repositories.phase2b_repository.find_open_wave_for_env", lambda *_a, **_k: None)
    payload, status = scanner_service.launch_scan_payload(3)
    assert status == 400
    assert "open, started wave" in payload["error"].lower()
