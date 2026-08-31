"""One analyze engagement per click. Repeater/Intruder ingest never starts this."""

import logging
from typing import Any, Dict, List, Tuple

from app.domain.burp.fields import enrich_clusters, event_fingerprint
from app.repositories import burp_repository, phase2b_repository
from app.services.burp_index import rewrite_index
from app.services.burp_service import tester_can_mint
from app.services.phase2b_service import get_wave, reject_if_closed

logger = logging.getLogger(__name__)

ACTIVE = {"naming", "pending", "queued", "running"}


def _top_host(clusters: List[Dict[str, Any]]) -> str:
    totals: Dict[str, int] = {}
    for item in clusters:
        host = str(item.get("host") or "")
        if not host:
            continue
        totals[host] = totals.get(host, 0) + int(item.get("count") or 0)
    if not totals:
        return ""
    return sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]


def _send_total(clusters: List[Dict[str, Any]]) -> int:
    return sum(int(item.get("count") or 0) for item in clusters)


def _name_job(job: Dict[str, Any], wave: Dict[str, Any], clusters: List[Dict[str, Any]]) -> str:
    from app.services.engagement_namer import app_and_wave_names, fallback_title, name_engagement

    host = _top_host(clusters)
    extra = f"{len(clusters)} clusters, {_send_total(clusters)} sends"
    try:
        burp_repository.update_job(int(job["id"]), status="naming")
        names = app_and_wave_names(wave)
        title = name_engagement(
            kind="analyze",
            host=host,
            wave_name=names["wave_name"],
            app_name=names["app_name"],
            host_count=len(clusters),
            extra=extra,
        )
    except Exception as exc:
        logger.info("Analyze job naming fell back: %s", exc)
        title = fallback_title(
            kind="analyze",
            host=host,
            host_count=len(clusters),
            wave_name=str((wave or {}).get("name") or ""),
        )
    burp_repository.update_job(int(job["id"]), status="pending", title=title)
    return title


def _narrative(clusters: List[Dict[str, Any]]) -> str:
    from app.services.engagement_namer import complete_text

    lines = []
    for item in clusters[:12]:
        statuses = ",".join(f"{code}:{n}" for code, n in (item.get("statuses") or {}).items())
        flags = ",".join(item.get("flags") or [])
        lines.append(
            f"{item.get('tool') or 'repeater'} {item.get('method')} {item.get('host')}{item.get('path')} "
            f"x{item.get('count')} [{statuses}] {flags}".strip()
        )
    prompt = (
        "Summarize a pentester's Burp Repeater and Intruder session for RAPTOR Live. "
        "Write two short sentences. No secrets, no JWT, no payloads, no headers. "
        "Say where they spent effort and what looked unusual (5xx, auth, Intruder).\n"
        + "\n".join(lines)
    )
    try:
        return str(complete_text(prompt, max_tokens=120) or "").strip()
    except Exception as exc:
        logger.info("Analyze narrative skipped: %s", exc)
        return ""


def _with_exchanges(clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from app.services.http_evidence import markdown_from_event

    for cluster in clusters:
        best = cluster.get("best")
        if not isinstance(best, dict) or best.get("exchange"):
            continue
        best["exchange"] = markdown_from_event(
            {
                "method": best.get("method"),
                "path": best.get("path"),
                "host": best.get("host"),
                "status": best.get("status"),
                "excerpt_json": {
                    "query": best.get("query") or "",
                    "headers": best.get("headers") if isinstance(best.get("headers"), dict) else {},
                    "body": best.get("body") or "",
                    "response_headers": best.get("response_headers")
                    if isinstance(best.get("response_headers"), dict)
                    else {},
                    "response_body": best.get("response_body") or "",
                },
            }
        )
    return clusters


def build_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    clusters = _with_exchanges(enrich_clusters(rows))
    return {
        "fingerprint": event_fingerprint(rows),
        "event_count": len(rows),
        "endpoint_count": len(clusters),
        "send_count": _send_total(clusters),
        "clusters": clusters,
    }


def queue_analyze_job(
    app_id: int,
    wave_id: int,
    username: str,
    role: str,
) -> Tuple[Dict[str, Any], int]:
    access, status = get_wave(app_id, wave_id, username=username, role=role)
    if status != 200:
        return access, status
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    closed = reject_if_closed(wave)
    if closed:
        return closed
    if not tester_can_mint(wave, username, role):
        return {"error": "Only testers on this wave can test Burp events."}, 403
    rows = burp_repository.list_events_for_wave(int(wave_id), limit=500)
    if not rows:
        return {"error": "No Burp events on this wave yet."}, 409
    fingerprint = event_fingerprint(rows)
    jobs = [item for item in burp_repository.list_jobs_for_wave(int(wave_id)) if item.get("kind") == "analyze"]
    active = next((item for item in jobs if str(item.get("status") or "") in ACTIVE), None)
    if active:
        return {
            "job_id": int(active["id"]),
            "engagement_id": f"burp:{active['id']}",
            "status": active.get("status") or "running",
            "coalesced": True,
        }, 200
    latest = next((item for item in jobs if str(item.get("status") or "") == "completed"), None)
    if latest:
        previous = latest.get("result_json") if isinstance(latest.get("result_json"), dict) else {}
        if str(previous.get("fingerprint") or "") == fingerprint:
            return {
                "job_id": int(latest["id"]),
                "engagement_id": f"burp:{latest['id']}",
                "status": "completed",
                "unchanged": True,
            }, 200
    summary = build_summary(rows)
    job_id = burp_repository.insert_job(
        wave_id=int(wave_id),
        application_id=int(app_id),
        agent_id=None,
        kind="analyze",
        host=summary["clusters"][0]["host"] if summary["clusters"] else "",
        path="",
        payload_json={"fingerprint": fingerprint},
    )
    from app.repositories.jobs_repository import enqueue_job

    enqueue_job("burp_analyze", {"burp_job_id": job_id})
    return {
        "job_id": job_id,
        "engagement_id": f"burp:{job_id}",
        "status": "queued",
    }, 202


def run_analyze_job(job_id: int) -> Dict[str, Any]:
    job = burp_repository.get_job(int(job_id))
    if not job:
        return {"error": "Analyze job not found."}
    wave = phase2b_repository.get_wave(int(job["wave_id"]))
    if not wave:
        burp_repository.update_job(int(job_id), status="failed", error="Wave not found.")
        return {"error": "Wave not found."}
    rows = burp_repository.list_events_for_wave(int(job["wave_id"]), limit=500)
    if not rows:
        burp_repository.update_job(int(job_id), status="failed", error="No Burp events on this wave yet.")
        return {"error": "No Burp events on this wave yet."}
    summary = build_summary(rows)
    _name_job(job, wave, summary["clusters"])
    burp_repository.update_job(int(job_id), status="running")
    rewrite_index(int(job["wave_id"]))
    result = dict(summary)
    result["narrative"] = _narrative(summary["clusters"])
    burp_repository.update_job(int(job_id), status="completed", result_json=result, error="")
    return {"job_id": int(job_id), "status": "completed", "endpoint_count": summary["endpoint_count"]}
