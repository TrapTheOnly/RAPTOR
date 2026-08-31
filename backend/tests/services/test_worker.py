from app import worker


def test_process_due_jobs_does_not_enqueue_dns_sync(monkeypatch):
    enqueued = []
    monkeypatch.setattr(worker, "enqueue_job", lambda *args, **kwargs: enqueued.append(args) or 1)
    monkeypatch.setattr(worker, "claim_next_job", lambda: None)

    worker.process_due_jobs()

    assert enqueued == []


def test_process_due_jobs_completes_claimed_dns_sync(monkeypatch):
    completed = []
    monkeypatch.setattr(
        worker,
        "claim_next_job",
        lambda: {"id": 9, "kind": "dns_sync"},
    )
    monkeypatch.setattr(worker, "_run_dns_sync", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "complete_job", lambda job_id: completed.append(job_id))
    monkeypatch.setattr(worker, "enqueue_job", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("enqueue")))

    worker.process_due_jobs()

    assert completed == [9]


def test_process_due_jobs_runs_burp_jwt(monkeypatch):
    ran = []
    completed = []
    monkeypatch.setattr(
        worker,
        "claim_next_job",
        lambda: {"id": 4, "kind": "burp_jwt", "payload": {"burp_job_id": 12}},
    )
    monkeypatch.setattr(
        "app.services.burp_jwt.run_jwt_job",
        lambda job_id: ran.append(job_id) or {"status": "completed", "proposal_id": 1},
    )
    monkeypatch.setattr(worker, "complete_job", lambda job_id: completed.append(job_id))
    monkeypatch.setattr(worker, "enqueue_job", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("enqueue")))

    worker.process_due_jobs()

    assert ran == [12]
    assert completed == [4]


def test_process_due_jobs_runs_burp_analyze(monkeypatch):
    ran = []
    completed = []
    monkeypatch.setattr(
        worker,
        "claim_next_job",
        lambda: {"id": 5, "kind": "burp_analyze", "payload": {"burp_job_id": 21}},
    )
    monkeypatch.setattr(
        "app.services.burp_analyze.run_analyze_job",
        lambda job_id: ran.append(job_id) or {"status": "completed", "endpoint_count": 2},
    )
    monkeypatch.setattr(worker, "complete_job", lambda job_id: completed.append(job_id))
    monkeypatch.setattr(worker, "enqueue_job", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("enqueue")))

    worker.process_due_jobs()

    assert ran == [21]
    assert completed == [5]
