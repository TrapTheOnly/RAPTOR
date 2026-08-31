from app.services import engagements_service


def test_list_engagements_merges_scan_and_burp(monkeypatch):
    monkeypatch.setattr(engagements_service, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(engagements_service, "scan_jobs_table_ready", lambda: True)
    monkeypatch.setattr(
        engagements_service,
        "list_scan_jobs",
        lambda wave_id: [
            {
                "id": 12,
                "status": "naming",
                "title": "",
                "record_ids": [1, 2],
                "launched_at": "2026-08-31T10:00:00",
                "last_error": "",
            }
        ],
    )
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "list_jobs_for_wave",
        lambda wave_id: [
            {
                "id": 4,
                "kind": "jwt",
                "status": "completed",
                "title": "Preprod JWT on api",
                "host": "api.example",
                "path": "/login",
                "created_at": "2026-08-31T11:00:00",
                "error": "",
                "result_json": {"proposal_id": 7, "kali": {"success": True, "hits": [], "suite": []}},
            }
        ],
    )
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "get_proposal_for_job",
        lambda job_id: {
            "id": 7,
            "title": "Preprod JWT on api",
            "description": "draft",
            "status": "pending",
            "finding_id": "",
            "result_json": {"success": True},
        },
    )
    monkeypatch.setattr(engagements_service.burp_repository, "list_events_for_wave", lambda *a, **k: [])
    monkeypatch.setattr(engagements_service.burp_repository, "list_proposals_for_wave", lambda *a, **k: [])
    monkeypatch.setattr(engagements_service.burp_repository, "count_events", lambda wave_id: 4)

    payload, status = engagements_service.list_engagements(1, 9, "ada", "pentester")
    assert status == 200
    rows = payload["engagements"]
    assert payload["burp_event_count"] == 4
    assert [item["id"] for item in rows] == ["burp:4", "scan:12"]
    assert rows[0]["proposal"]["id"] == 7
    assert rows[0]["result"]["success"] is True
    assert rows[1]["title"] == "Naming…"


def test_accept_proposal_files_human_finding(monkeypatch):
    monkeypatch.setattr(engagements_service, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(engagements_service, "wave_is_open", lambda wave: True)
    monkeypatch.setattr(
        engagements_service.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open"},
    )
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "get_job",
        lambda job_id: {
            "id": job_id,
            "wave_id": 9,
            "host": "api.example",
            "title": "Preprod JWT on api",
        },
    )
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "get_proposal_for_job",
        lambda job_id: {
            "id": 7,
            "title": "Preprod JWT on api",
            "description": "jwt_tool cracked a weak HMAC secret: secret.",
            "finding_id": "",
            "result_json": {
                "hits": [{"step": "weak_secret", "kind": "weak_secret", "detail": "secret"}],
                "suite": [{"step": "weak_secret", "return_code": 0, "stdout": "[+] secret is the CORRECT key!"}],
            },
        },
    )
    monkeypatch.setattr(
        engagements_service.phase2b_repository,
        "list_live_wave_hosts",
        lambda wave: [{"id": 44, "name": "api.example"}],
    )
    monkeypatch.setattr(
        "app.repositories.vuln_categories_repository.fetch_vuln_categories",
        lambda: [{"id": 9, "name": "Broken Authentication"}],
    )
    created = {}
    monkeypatch.setattr(
        "app.services.app_program_service.create_finding",
        lambda app_id, data, username, role: created.update(data)
        or ({"finding": {"id": "f-1", "title": data["title"]}}, 201),
    )
    updated = {}
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "update_proposal",
        lambda proposal_id, **kwargs: updated.update({"id": proposal_id, **kwargs}),
    )
    monkeypatch.setattr(
        "app.services.terminal_shot.attach_jwt_screenshots",
        lambda suite, hits=None: [
            {
                "step": "weak_secret",
                "alt": "jwt_tool HMAC dictionary crack",
                "url": "/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png",
            }
        ],
    )
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "latest_http_event",
        lambda *args, **kwargs: None,
    )

    payload, status = engagements_service.accept_proposal(1, 9, 4, "ada", "pentester")
    assert status == 201
    assert created["source"] == "human"
    assert created["record_id"] == 44
    assert created["title"] == "Weak JWT HMAC secret on api.example"
    assert "impersonate" in created["impact"]
    assert "###" not in created["evidence"]
    assert "```shell" in created["evidence"]
    assert created["evidence"].index("```shell") < created["evidence"].index(
        "![jwt_tool HMAC dictionary crack](/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png)"
    )
    assert "Recovered secret" not in created["evidence"]
    assert created["category_name"] == "Broken Authentication"
    assert created["category_id"] == 9
    assert created["base_score"] == 9.1
    assert payload["finding"]["id"] == "f-1"
    assert updated["finding_id"] == "f-1"
    assert updated["status"] == "accepted"


def test_accept_proposal_rejects_when_suite_found_nothing(monkeypatch):
    monkeypatch.setattr(engagements_service, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(engagements_service, "wave_is_open", lambda wave: True)
    monkeypatch.setattr(
        engagements_service.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open"},
    )
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "get_job",
        lambda job_id: {"id": job_id, "wave_id": 9, "host": "api.example"},
    )
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "get_proposal_for_job",
        lambda job_id: {
            "id": 7,
            "title": "JWT suite on example.com",
            "description": "Kali jwt_tool finished a fixed suite",
            "finding_id": "",
            "result_json": {"success": True, "suite": []},
        },
    )

    payload, status = engagements_service.accept_proposal(1, 9, 4, "ada", "pentester")
    assert status == 409
    assert "no JWT weakness" in payload["error"]


def test_list_engagements_includes_scanner_proposals(monkeypatch):
    monkeypatch.setattr(engagements_service, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(engagements_service, "scan_jobs_table_ready", lambda: False)
    monkeypatch.setattr(engagements_service.burp_repository, "list_jobs_for_wave", lambda wave_id: [])
    monkeypatch.setattr(engagements_service.burp_repository, "list_events_for_wave", lambda *a, **k: [])
    monkeypatch.setattr(
        engagements_service.burp_repository,
        "list_proposals_for_wave",
        lambda wave_id, kind="": [
            {
                "id": 19,
                "kind": "scanner",
                "job_id": None,
                "title": "SQL injection on app.example",
                "description": "SQLi",
                "status": "pending",
                "finding_id": "",
                "created_at": "2026-08-31T12:00:00",
                "result_json": {"host": "app.example", "path": "/login", "exchange": "```http\nPOST /login\n```\n"},
            }
        ],
    )
    monkeypatch.setattr(engagements_service.burp_repository, "count_events", lambda wave_id: 1)
    payload, status = engagements_service.list_engagements(1, 9, "ada", "pentester")
    assert status == 200
    assert payload["engagements"][0]["id"] == "proposal:19"
    assert payload["engagements"][0]["kind"] == "scanner"


def test_accept_scanner_proposal_files_human_finding(monkeypatch):
    monkeypatch.setattr(
        "app.services.burp_evidence.get_wave",
        lambda *args, **kwargs: ({"wave": {}}, 200),
    )
    monkeypatch.setattr("app.services.burp_evidence.wave_is_open", lambda wave: True)
    monkeypatch.setattr(
        "app.services.burp_evidence.phase2b_repository.get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open"},
    )
    monkeypatch.setattr(
        "app.services.burp_evidence.burp_repository.get_proposal",
        lambda proposal_id: {
            "id": proposal_id,
            "wave_id": 9,
            "kind": "scanner",
            "title": "SQL injection on app.example",
            "description": "SQLi",
            "finding_id": "",
            "result_json": {
                "host": "app.example",
                "path": "/login",
                "writeup": {
                    "title": "SQL injection on app.example",
                    "description": "SQLi on `/login`.",
                    "impact": "",
                    "evidence": "```http\nPOST /login HTTP/1.1\n\n===\n\nHTTP/1.1 200\n```\n",
                    "remediation": "",
                    "category_name": "SQL injection",
                },
            },
        },
    )
    monkeypatch.setattr("app.services.burp_evidence.record_id_for_host", lambda wave, host: 44)
    created = {}
    monkeypatch.setattr(
        "app.services.app_program_service.create_finding",
        lambda app_id, data, username, role: created.update(data)
        or ({"finding": {"id": "f-sql", "title": data["title"]}}, 201),
    )
    updated = {}
    monkeypatch.setattr(
        "app.services.burp_evidence.burp_repository.update_proposal",
        lambda proposal_id, **kwargs: updated.update({"id": proposal_id, **kwargs}),
    )
    payload, status = engagements_service.accept_scanner_proposal(1, 9, 19, "ada", "pentester")
    assert status == 201
    assert created["source"] == "human"
    assert created["status"] == "open"
    assert created["record_id"] == 44
    assert "POST /login" in created["evidence"]
    assert payload["finding"]["id"] == "f-sql"
    assert updated["finding_id"] == "f-sql"
