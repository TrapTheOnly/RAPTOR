import json
import logging
import threading
import time
from typing import Any, Dict, Optional

from app.repositories.jobs_repository import (
    claim_next_job,
    complete_job,
    enqueue_job,
    fail_job,
    has_pending_or_running,
)

logger = logging.getLogger(__name__)

_loop_started = False
_loop_lock = threading.Lock()


def _poll_interval_seconds() -> int:
    return 300


def _ensure_dns_sync_job() -> None:
    if has_pending_or_running("dns_sync"):
        return
    enqueue_job("dns_sync", {})


def _job_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    raw = job.get("payload")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _run_dns_sync(payload: Optional[Dict[str, Any]] = None) -> None:
    from app.services.cloud_dns_service import sync_all_pull_sources, sync_pull_source

    data = payload or {}
    source_id = data.get("source_id")
    if source_id not in (None, ""):
        sync_pull_source(int(source_id), force=True)
        return
    sync_all_pull_sources(force=False)


def process_due_jobs() -> None:
    job = claim_next_job()
    if not job:
        return
    job_id = int(job["id"])
    kind = str(job.get("kind") or "")
    try:
        if kind == "dns_sync":
            _run_dns_sync(_job_payload(job))
        elif kind == "burp_jwt":
            from app.services.burp_jwt import run_jwt_job

            burp_job_id = int(_job_payload(job).get("burp_job_id") or 0)
            if not burp_job_id:
                raise RuntimeError("burp_jwt job missing burp_job_id")
            result = run_jwt_job(burp_job_id)
            if result.get("error") and result.get("status") != "completed":
                raise RuntimeError(str(result.get("error")))
        elif kind == "burp_analyze":
            from app.services.burp_analyze import run_analyze_job

            burp_job_id = int(_job_payload(job).get("burp_job_id") or 0)
            if not burp_job_id:
                raise RuntimeError("burp_analyze job missing burp_job_id")
            result = run_analyze_job(burp_job_id)
            if result.get("error") and result.get("status") != "completed":
                raise RuntimeError(str(result.get("error")))
        else:
            raise RuntimeError(f"Unknown job kind: {kind}")
        complete_job(job_id)
    except Exception as exc:
        logger.error("Job %s (%s) failed: %s", job_id, kind, exc)
        fail_job(job_id, str(exc))


def _loop() -> None:
    interval = _poll_interval_seconds()
    last_periodic = time.time()
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
