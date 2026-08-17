import logging
import os
import threading
import time
from typing import Optional

from app.repositories.jobs_repository import (
    claim_next_job,
    complete_job,
    enqueue_job,
    fail_job,
    has_pending_or_running,
)
from app.services.audit_service import record_audit_event

logger = logging.getLogger(__name__)

_loop_started = False
_loop_lock = threading.Lock()


def _update_interval_seconds() -> int:
    try:
        return max(30, int(os.getenv("UPDATE_TIME", "86400")))
    except ValueError:
        return 86400


def _ensure_dns_sync_job() -> None:
    if has_pending_or_running("dns_sync"):
        return
    enqueue_job("dns_sync", {})


def _run_dns_sync() -> None:
    from app.services.dns_sync_service import update_data

    update_data()
    record_audit_event(
        actor="system",
        actor_type="worker",
        action="ingest.dns_sync",
        entity_type="dns_source",
        entity_id="bind_file",
        metadata={},
    )


def process_due_jobs() -> None:
    _ensure_dns_sync_job()
    job = claim_next_job()
    if not job:
        return
    job_id = int(job["id"])
    kind = str(job.get("kind") or "")
    try:
        if kind == "dns_sync":
            _run_dns_sync()
        else:
            raise RuntimeError(f"Unknown job kind: {kind}")
        complete_job(job_id)
    except Exception as exc:
        logger.error("Job %s (%s) failed: %s", job_id, kind, exc)
        fail_job(job_id, str(exc))


def _loop() -> None:
    interval = _update_interval_seconds()
    last_periodic = 0.0
    while True:
        now = time.time()
        if now - last_periodic >= interval:
            _ensure_dns_sync_job()
            last_periodic = now
        try:
            process_due_jobs()
        except Exception as exc:
            logger.error("Job loop error: %s", exc)
        time.sleep(5)


def start_job_loop() -> Optional[threading.Thread]:
    global _loop_started
    with _loop_lock:
        if _loop_started:
            return None
        _loop_started = True
    _ensure_dns_sync_job()
    thread = threading.Thread(target=_loop, name="raptor-jobs", daemon=True)
    thread.start()
    logger.info("RAPTOR job loop started")
    return thread


__all__ = ["process_due_jobs", "start_job_loop"]
