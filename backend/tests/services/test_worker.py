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
