from app.services import burp_analyze


def test_queue_analyze_rejects_empty_wave(monkeypatch):
    monkeypatch.setattr(burp_analyze, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(
        burp_analyze.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open", "opened_by": "ada", "members": ["ada"]},
    )
    monkeypatch.setattr(burp_analyze, "reject_if_closed", lambda wave: None)
    monkeypatch.setattr(burp_analyze, "tester_can_mint", lambda *args, **kwargs: True)
    monkeypatch.setattr(burp_analyze.burp_repository, "list_events_for_wave", lambda *args, **kwargs: [])
    payload, status = burp_analyze.queue_analyze_job(1, 9, "ada", "pentester")
    assert status == 409
    assert "No Burp events" in payload["error"]


def test_queue_analyze_coalesces_active_job(monkeypatch):
    monkeypatch.setattr(burp_analyze, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(
        burp_analyze.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open", "opened_by": "ada", "members": ["ada"]},
    )
    monkeypatch.setattr(burp_analyze, "reject_if_closed", lambda wave: None)
    monkeypatch.setattr(burp_analyze, "tester_can_mint", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        burp_analyze.burp_repository,
        "list_events_for_wave",
        lambda *args, **kwargs: [
            {"id": 1, "tool": "repeater", "method": "GET", "host": "app.example", "path": "/x", "status": 200, "count": 3}
        ],
    )
    monkeypatch.setattr(
        burp_analyze.burp_repository,
        "list_jobs_for_wave",
        lambda wave_id: [{"id": 44, "kind": "analyze", "status": "running"}],
    )
    created = []
    monkeypatch.setattr(burp_analyze.burp_repository, "insert_job", lambda **kwargs: created.append(kwargs) or 99)
    payload, status = burp_analyze.queue_analyze_job(1, 9, "ada", "pentester")
    assert status == 200
    assert payload["coalesced"] is True
    assert payload["job_id"] == 44
    assert created == []


def test_queue_analyze_skips_when_fingerprint_unchanged(monkeypatch):
    rows = [
        {"id": 1, "tool": "repeater", "method": "GET", "host": "app.example", "path": "/x", "status": 200, "count": 3}
    ]
    summary = burp_analyze.build_summary(rows)
    monkeypatch.setattr(burp_analyze, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(
        burp_analyze.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open", "opened_by": "ada", "members": ["ada"]},
    )
    monkeypatch.setattr(burp_analyze, "reject_if_closed", lambda wave: None)
    monkeypatch.setattr(burp_analyze, "tester_can_mint", lambda *args, **kwargs: True)
    monkeypatch.setattr(burp_analyze.burp_repository, "list_events_for_wave", lambda *args, **kwargs: rows)
    monkeypatch.setattr(
        burp_analyze.burp_repository,
        "list_jobs_for_wave",
        lambda wave_id: [
            {
                "id": 8,
                "kind": "analyze",
                "status": "completed",
                "result_json": {"fingerprint": summary["fingerprint"]},
            }
        ],
    )
    payload, status = burp_analyze.queue_analyze_job(1, 9, "ada", "pentester")
    assert status == 200
    assert payload["unchanged"] is True
    assert payload["job_id"] == 8


def test_queue_analyze_enqueues_one_job(monkeypatch):
    monkeypatch.setattr(burp_analyze, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(
        burp_analyze.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open", "opened_by": "ada", "members": ["ada"]},
    )
    monkeypatch.setattr(burp_analyze, "reject_if_closed", lambda wave: None)
    monkeypatch.setattr(burp_analyze, "tester_can_mint", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        burp_analyze.burp_repository,
        "list_events_for_wave",
        lambda *args, **kwargs: [
            {"id": 1, "tool": "repeater", "method": "POST", "host": "app.example", "path": "/login", "status": 401, "count": 4}
        ],
    )
    monkeypatch.setattr(burp_analyze.burp_repository, "list_jobs_for_wave", lambda wave_id: [])
    created = {}
    monkeypatch.setattr(burp_analyze.burp_repository, "insert_job", lambda **kwargs: created.update(kwargs) or 21)
    queued = []
    monkeypatch.setattr("app.repositories.jobs_repository.enqueue_job", lambda kind, payload: queued.append((kind, payload)) or 3)
    payload, status = burp_analyze.queue_analyze_job(1, 9, "ada", "pentester")
    assert status == 202
    assert payload["job_id"] == 21
    assert created["kind"] == "analyze"
    assert queued == [("burp_analyze", {"burp_job_id": 21})]


def test_run_analyze_job_stores_clusters_not_proposals(monkeypatch):
    rows = [
        {"id": 1, "tool": "repeater", "method": "POST", "host": "app.example", "path": "/login", "status": 401, "count": 4},
        {"id": 2, "tool": "intruder", "method": "POST", "host": "app.example", "path": "/login", "status": 500, "count": 1},
    ]
    monkeypatch.setattr(
        burp_analyze.burp_repository,
        "get_job",
        lambda job_id: {"id": job_id, "wave_id": 9, "kind": "analyze", "host": "app.example"},
    )
    monkeypatch.setattr(
        burp_analyze.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "name": "Test"},
    )
    monkeypatch.setattr(burp_analyze.burp_repository, "list_events_for_wave", lambda *args, **kwargs: rows)
    monkeypatch.setattr(burp_analyze, "_name_job", lambda job, wave, clusters: "Burp analyze · 1 endpoint")
    monkeypatch.setattr(burp_analyze, "_narrative", lambda clusters: "Most of the session was POST /login.")
    monkeypatch.setattr(burp_analyze, "rewrite_index", lambda wave_id: None)
    updates = []
    monkeypatch.setattr(burp_analyze.burp_repository, "update_job", lambda *args, **kwargs: updates.append(kwargs))
    result = burp_analyze.run_analyze_job(21)
    assert result["status"] == "completed"
    stored = [item for item in updates if item.get("status") == "completed"][-1]
    assert stored["result_json"]["endpoint_count"] == 2
    tools = {item["tool"]: item["count"] for item in stored["result_json"]["clusters"]}
    assert tools == {"repeater": 4, "intruder": 1}
    assert stored["result_json"]["narrative"] == "Most of the session was POST /login."
    assert "proposal" not in stored
    cluster = stored["result_json"]["clusters"][0]
    assert "best" in cluster
    assert "deltas" in cluster
