"""Wave engagements: AI scans and Burp jobs, listed for the live view."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.domain.burp.fields import normalize_host
from app.repositories import burp_repository, phase2b_repository
from app.repositories.scan_jobs_repository import list_jobs_for_wave as list_scan_jobs, scan_jobs_table_ready
from app.services.phase2b_service import get_wave, wave_is_open

logger = logging.getLogger(__name__)


def _iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def _sort_key(item: Dict[str, Any]) -> str:
    return str(item.get("created_at") or "")


def _scan_item(row: Dict[str, Any]) -> Dict[str, Any]:
    status = str(row.get("status") or "idle")
    error = str(row.get("last_error") or "")
    if error == "stopped":
        status = "stopped"
    title = str(row.get("title") or "").strip()
    host_count = len(row.get("record_ids") or [])
    if not title:
        title = "Naming…" if status in {"naming", "pending", "queued"} else "AI scan"
    return {
        "id": f"scan:{row.get('id')}",
        "source": "scan",
        "source_id": int(row.get("id") or 0),
        "kind": "ai_scan",
        "title": title,
        "status": status,
        "host": "",
        "path": "",
        "host_count": host_count,
        "error": error,
        "created_at": _iso(row.get("launched_at")),
        "proposal": None,
    }


def _kali_result(row: Dict[str, Any], proposal: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    job_res = row.get("result_json") if isinstance(row.get("result_json"), dict) else {}
    if isinstance(job_res.get("kali"), dict):
        return job_res["kali"]
    if "suite" in job_res or "hits" in job_res:
        return job_res
    if proposal and isinstance(proposal.get("result_json"), dict):
        return proposal["result_json"]
    return {}


def _proposal_public(proposal: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not proposal:
        return None
    return {
        "id": int(proposal.get("id") or 0),
        "title": proposal.get("title") or "",
        "description": proposal.get("description") or "",
        "status": proposal.get("status") or "pending",
        "finding_id": proposal.get("finding_id") or "",
        "result": proposal.get("result_json") if isinstance(proposal.get("result_json"), dict) else {},
    }


def _burp_item(
    row: Dict[str, Any],
    proposal: Optional[Dict[str, Any]],
    workbench: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    title = str(row.get("title") or "").strip()
    status = str(row.get("status") or "pending")
    kind = str(row.get("kind") or "jwt")
    if not title:
        title = "Naming…" if status in {"pending", "naming"} else kind.upper()
    return {
        "id": f"burp:{row.get('id')}",
        "source": "burp",
        "source_id": int(row.get("id") or 0),
        "kind": kind,
        "title": title,
        "status": status,
        "host": row.get("host") or "",
        "path": row.get("path") or "",
        "host_count": 0,
        "error": row.get("error") or "",
        "created_at": _iso(row.get("created_at")),
        "proposal": _proposal_public(proposal),
        "result": _job_result(row, proposal, workbench=workbench),
    }


def _scanner_item(proposal: Dict[str, Any]) -> Dict[str, Any]:
    result = proposal.get("result_json") if isinstance(proposal.get("result_json"), dict) else {}
    finding_id = str(proposal.get("finding_id") or "")
    status = "accepted" if finding_id else str(proposal.get("status") or "pending")
    return {
        "id": f"proposal:{proposal.get('id')}",
        "source": "burp",
        "source_id": int(proposal.get("id") or 0),
        "kind": "scanner",
        "title": proposal.get("title") or "Scanner issue",
        "status": status,
        "host": result.get("host") or "",
        "path": result.get("path") or "",
        "host_count": 0,
        "error": "",
        "created_at": _iso(proposal.get("created_at")),
        "proposal": _proposal_public(proposal),
        "result": result,
    }


def _job_result(
    row: Dict[str, Any],
    proposal: Optional[Dict[str, Any]],
    workbench: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if str(row.get("kind") or "") == "analyze":
        stored = dict(row.get("result_json") or {}) if isinstance(row.get("result_json"), dict) else {}
        if workbench and workbench.get("clusters"):
            stored = dict(stored)
            stored["clusters"] = workbench.get("clusters") or []
            stored["event_count"] = workbench.get("event_count", stored.get("event_count"))
            stored["endpoint_count"] = workbench.get("endpoint_count", stored.get("endpoint_count"))
            stored["send_count"] = workbench.get("send_count", stored.get("send_count"))
        return stored
    return _kali_result(row, proposal)


def list_engagements(app_id: int, wave_id: int, username: str, role: str) -> Tuple[Dict[str, Any], int]:
    access, status = get_wave(app_id, wave_id, username=username, role=role)
    if status != 200:
        return access, status
    items: List[Dict[str, Any]] = []
    if scan_jobs_table_ready():
        for row in list_scan_jobs(wave_id):
            items.append(_scan_item(row))
    events = burp_repository.list_events_for_wave(wave_id, limit=500)
    workbench = None
    if events:
        from app.services.burp_analyze import build_summary

        workbench = build_summary(events)
    for row in burp_repository.list_jobs_for_wave(wave_id):
        proposal = burp_repository.get_proposal_for_job(int(row["id"]))
        items.append(_burp_item(row, proposal, workbench=workbench))
    for proposal in burp_repository.list_proposals_for_wave(wave_id, kind="scanner"):
        if proposal.get("job_id"):
            continue
        items.append(_scanner_item(proposal))
    items.sort(key=_sort_key, reverse=True)
    return {
        "engagements": items,
        "wave_id": wave_id,
        "burp_event_count": burp_repository.count_events(wave_id),
    }, 200


def get_engagement(
    app_id: int, wave_id: int, engagement_id: str, username: str, role: str
) -> Tuple[Dict[str, Any], int]:
    listed, status = list_engagements(app_id, wave_id, username, role)
    if status != 200:
        return listed, status
    wanted = str(engagement_id or "").strip()
    for item in listed.get("engagements") or []:
        if item.get("id") == wanted:
            return {"engagement": item}, 200
    return {"error": "Engagement not found."}, 404


def accept_proposal(
    app_id: int,
    wave_id: int,
    job_id: int,
    username: str,
    role: str,
) -> Tuple[Dict[str, Any], int]:
    from app.services.app_program_service import create_finding

    access, status = get_wave(app_id, wave_id, username=username, role=role)
    if status != 200:
        return access, status
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    if not wave_is_open(wave):
        return {"error": "This wave has ended. Findings and wave details are read-only."}, 400
    job = burp_repository.get_job(int(job_id))
    if not job or int(job.get("wave_id") or 0) != int(wave_id):
        return {"error": "Engagement not found."}, 404
    proposal = burp_repository.get_proposal_for_job(int(job_id))
    if not proposal:
        return {"error": "This engagement has no proposal yet."}, 409
    from app.services.burp_jwt import finding_writeup, suite_hits

    result = proposal.get("result_json") if isinstance(proposal.get("result_json"), dict) else {}
    hits = suite_hits(result)
    if not hits:
        return {"error": "This suite found no JWT weakness to file."}, 409
    if proposal.get("finding_id"):
        return {"finding_id": proposal.get("finding_id"), "already_accepted": True}, 200
    host = normalize_host(str(job.get("host") or ""))
    record_id = None
    for row in phase2b_repository.list_live_wave_hosts(wave):
        name = normalize_host(str(row.get("name") or ""))
        if name == host:
            record_id = int(row["id"])
            break
    if not record_id:
        return {"error": "No in-scope host matches this engagement."}, 400
    suite = result.get("suite") if isinstance(result.get("suite"), list) else []
    screenshots: List[Dict[str, str]] = []
    try:
        from app.services.terminal_shot import attach_jwt_screenshots

        screenshots = attach_jwt_screenshots(suite, hits)
    except Exception as exc:
        logger.info("JWT evidence screenshots skipped: %s", exc)
    from app.services.burp_jwt import _http_exchange_for_job

    writeup = finding_writeup(
        host=str(job.get("host") or ""),
        path=str(job.get("path") or ""),
        hits=hits,
        suite=suite,
        screenshots=screenshots,
        http_exchange=_http_exchange_for_job(job),
    )
    category_id = ""
    try:
        from app.repositories.vuln_categories_repository import fetch_vuln_categories

        wanted = str(writeup.get("category_name") or "").strip().lower()
        for row in fetch_vuln_categories():
            if str(row.get("name") or "").strip().lower() == wanted:
                category_id = row.get("id") or ""
                break
    except Exception:
        category_id = ""
    payload, created_status = create_finding(
        app_id,
        {
            "record_id": record_id,
            "wave_id": wave_id,
            "title": writeup["title"],
            "description": writeup["description"],
            "impact": writeup["impact"],
            "evidence": writeup["evidence"],
            "remediation": writeup["remediation"],
            "category_id": category_id,
            "category_name": writeup["category_name"],
            "metrics": writeup["metrics"],
            "base_score": writeup["base_score"],
            "source": "human",
            "status": "open",
        },
        username,
        role,
    )
    if created_status != 201:
        return payload, created_status
    finding = payload.get("finding") or {}
    finding_id = str(finding.get("id") or "")
    burp_repository.update_proposal(int(proposal["id"]), status="accepted", finding_id=finding_id)
    return {"finding": finding, "proposal_id": int(proposal["id"])}, 201


def accept_scanner_proposal(
    app_id: int,
    wave_id: int,
    proposal_id: int,
    username: str,
    role: str,
) -> Tuple[Dict[str, Any], int]:
    from app.services.burp_evidence import accept_scanner_proposal as _accept

    return _accept(app_id, wave_id, proposal_id, username, role)
