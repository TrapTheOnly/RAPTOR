from app.services import app_report_service as svc


def test_owner_delivery_omits_qa_only_and_drafts(monkeypatch):
    findings = [
        {
            "id": "prod-finding",
            "status": "open",
            "baseScore": 9.8,
            "title": "CORS",
            "occurrences": [
                {"record_id": 1, "dns_name": "www.google.com", "environment_slug": "prod"},
                {"record_id": 2, "dns_name": "qa.google.com", "environment_slug": "qa"},
            ],
        },
        {
            "id": "qa-only",
            "status": "open",
            "baseScore": 9.1,
            "title": "QA XSS",
            "occurrences": [
                {"record_id": 2, "dns_name": "qa.google.com", "environment_slug": "qa"},
            ],
        },
        {
            "id": "draft",
            "status": "draft",
            "baseScore": 9.8,
            "title": "Draft",
            "occurrences": [
                {"record_id": 1, "dns_name": "www.google.com", "environment_slug": "prod"},
            ],
        },
    ]
    monkeypatch.setattr(
        svc.pentest_findings_repository,
        "fetch_app_findings",
        lambda *args, **kwargs: (findings, 3),
    )

    def _split(occurrences, selected_env_ids):
        primary = [item for item in occurrences if item.get("environment_slug") == "prod"]
        observed = [
            item
            for item in occurrences
            if item.get("environment_slug") not in {"prod", "unassigned"}
        ]
        return {"primary": primary, "observed": observed}

    monkeypatch.setattr(svc, "_split_occurrences", _split)
    packed, excluded_drafts, _unassigned, _total = svc._pack_findings(1, [10], include_drafts=False)
    ids = [item["id"] for item in packed]
    assert ids == ["prod-finding"]
    assert packed[0]["also_observed"][0]["dns_name"] == "qa.google.com"
    assert excluded_drafts == 1


def test_generate_scoped_report_writes_report_exports(monkeypatch):
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

    monkeypatch.setattr(svc, "get_db_connection", lambda _path: Conn())
    monkeypatch.setattr(svc.applications_repository, "fetch_application", lambda _id: {"id": 1, "name": "Google", "roe_link": ""})
    monkeypatch.setattr(
        svc,
        "_default_env_ids",
        lambda _app_id, _requested: ([9], [{"id": 9, "slug": "prod", "is_production": True}]),
    )
    monkeypatch.setattr(svc, "visible_env_ids", lambda *_a, **_k: None)
    monkeypatch.setattr(svc, "_pack_findings", lambda *args, **kwargs: ([{"id": "f1", "title": "CORS", "occurrences": [], "also_observed": []}], 0, [], 1))
    monkeypatch.setattr(svc, "safe_json_load", lambda *_args, **_kwargs: {"blocks": []})
    monkeypatch.setattr(svc, "bind_report_template_logo_for_template", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(svc, "render_pentest_report_pdf", lambda *_args, **_kwargs: b"%PDF")
    monkeypatch.setattr(svc, "load_enabled_checklist_templates", lambda: [])
    monkeypatch.setattr(svc, "save_report", lambda *_args, **_kwargs: "reports/app-1.pdf")

    payload, status = svc.generate_scoped_report(
        scope_kind="application",
        scope_id=1,
        data={},
        username="alice",
    )
    assert status == 200
    assert payload["export_id"] == 44
    assert inserts
    assert inserts[0][0] == "application"
    assert inserts[0][1] == 1
