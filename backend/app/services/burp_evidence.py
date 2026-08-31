"""File Burp HTTP as finding evidence. Never stores compact JWTs."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Tuple

from app.repositories import burp_repository, pentest_findings_repository, phase2b_repository
from app.services.burp_service import (
    _normalize_event,
    host_in_scope,
    record_id_for_host,
)
from app.services.http_evidence import markdown_from_event
from app.services.phase2b_service import get_wave, reject_if_closed, wave_is_open

logger = logging.getLogger(__name__)


def _plain(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", str(text or ""))
    return re.sub(r"\s+", " ", cleaned).strip()


def _event_row_as_markdown(event: Dict[str, Any]) -> str:
    return markdown_from_event(event)


def list_drafts_for_agent(agent: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    wave = phase2b_repository.get_wave(int(agent["wave_id"]))
    closed = reject_if_closed(wave)
    if closed:
        return closed
    username = str(agent.get("username") or "").strip()
    findings, _total = pentest_findings_repository.fetch_app_findings(
        int(agent["application_id"]),
        wave_id=int(agent["wave_id"]),
        status="draft",
        include_drafts=True,
        limit=20,
    )
    drafts = []
    for item in findings:
        if username and str(item.get("created_by") or "") != username:
            continue
        drafts.append({"id": item.get("id"), "title": item.get("title") or "Draft"})
    return {"drafts": drafts}, 200


def list_drafts_session(
    app_id: int, wave_id: int, username: str, role: str
) -> Tuple[Dict[str, Any], int]:
    access, status = get_wave(app_id, wave_id, username=username, role=role)
    if status != 200:
        return access, status
    actor = str(username or "").strip()
    findings, _total = pentest_findings_repository.fetch_app_findings(
        int(app_id),
        wave_id=int(wave_id),
        status="draft",
        include_drafts=True,
        limit=20,
    )
    drafts = []
    for item in findings:
        if actor and str(item.get("created_by") or "") != actor:
            continue
        drafts.append({"id": item.get("id"), "title": item.get("title") or "Draft"})
    return {"drafts": drafts}, 200


def _store_event(agent: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    from app.services import burp_index

    stored = burp_repository.upsert_event(
        wave_id=int(agent["wave_id"]),
        application_id=int(agent["application_id"]),
        agent_id=int(agent["id"]),
        **event,
    )
    burp_index.rewrite_index(int(agent["wave_id"]))
    return stored


def _attach_or_create(
    *,
    wave: Dict[str, Any],
    application_id: int,
    wave_id: int,
    username: str,
    role: str,
    event: Dict[str, Any],
    finding_id: str = "",
) -> Tuple[Dict[str, Any], int]:
    from app.services.app_program_service import create_finding, patch_finding

    record_id = record_id_for_host(wave, str(event.get("host") or ""))
    if not record_id:
        return {"error": "No in-scope host matches this traffic."}, 400
    markdown = _event_row_as_markdown(event)
    if not markdown.strip():
        return {"error": "That request has no HTTP to file."}, 400
    wanted = str(finding_id or "").strip()
    if wanted:
        current = pentest_findings_repository.get_finding(wanted)
        if not current:
            return {"error": "Finding not found."}, 404
        if int(current.get("application_id") or 0) != int(application_id):
            return {"error": "Finding is not on this application."}, 400
        if int(current.get("discovered_wave_id") or 0) != int(wave_id):
            return {"error": "Finding is not on this wave."}, 400
        if str(current.get("status") or "") != "draft":
            return {"error": "Only draft findings can take Burp evidence this way."}, 400
        existing = str(current.get("evidence") or "").rstrip()
        combined = f"{existing}\n\n{markdown}".strip() if existing else markdown
        payload, status_code = patch_finding(wanted, {"evidence": combined}, username, role)
        if status_code != 200:
            return payload, status_code
        finding = payload.get("finding") or current
        return {
            "finding_id": finding.get("id") or wanted,
            "application_id": application_id,
            "finding": finding,
        }, 200
    method = str(event.get("method") or "GET").strip().upper() or "GET"
    host = str(event.get("host") or "")
    path = str(event.get("path") or "/")
    status = event.get("status")
    if status is not None and str(status) != "":
        description = f"{method} `{host}{path}` returned {status}."
    else:
        description = f"{method} `{host}{path}`."
    payload, created_status = create_finding(
        application_id,
        {
            "record_id": record_id,
            "wave_id": wave_id,
            "title": f"{method} {path} on {host}"[:200],
            "description": description,
            "impact": "",
            "evidence": markdown,
            "remediation": "",
            "source": "human",
            "status": "draft",
        },
        username,
        role,
    )
    if created_status != 201:
        return payload, created_status
    finding = payload.get("finding") or {}
    return {
        "finding_id": finding.get("id") or "",
        "application_id": application_id,
        "finding": finding,
    }, 201


def file_evidence_for_agent(agent: Dict[str, Any], data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    wave = phase2b_repository.get_wave(int(agent["wave_id"]))
    closed = reject_if_closed(wave)
    if closed:
        return closed
    event = _normalize_event({**data, "tool": data.get("tool") or "repeater"}, allow_static=True)
    if not event:
        return {"error": "host, path, and method are required."}, 400
    if not host_in_scope(wave or {}, event["host"]):
        return {"error": "Host is out of wave scope."}, 400
    stored = _store_event(agent, event)
    merged = dict(event)
    if stored.get("id") is not None:
        merged["id"] = stored.get("id")
    if stored.get("status") is not None:
        merged["status"] = stored.get("status")
    if isinstance(stored.get("excerpt_json"), dict):
        merged["excerpt_json"] = stored["excerpt_json"]
    return _attach_or_create(
        wave=wave or {},
        application_id=int(agent["application_id"]),
        wave_id=int(agent["wave_id"]),
        username=str(agent.get("username") or "unknown"),
        role="",
        event=merged,
        finding_id=str(data.get("finding_id") or ""),
    )


def file_evidence_session(
    app_id: int,
    wave_id: int,
    username: str,
    role: str,
    data: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    access, status = get_wave(app_id, wave_id, username=username, role=role)
    if status != 200:
        return access, status
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    if not wave_is_open(wave):
        return {"error": "This wave has ended. Findings and wave details are read-only."}, 400
    try:
        event_id = int(data.get("event_id"))
    except (TypeError, ValueError):
        return {"error": "event_id is required."}, 400
    event = burp_repository.get_event(event_id, wave_id=wave_id)
    if not event:
        return {"error": "Burp event not found."}, 404
    return _attach_or_create(
        wave=wave,
        application_id=int(app_id),
        wave_id=int(wave_id),
        username=username,
        role=role,
        event=event,
        finding_id=str(data.get("finding_id") or ""),
    )


def scanner_writeup(event: Dict[str, Any]) -> Dict[str, str]:
    name = str(event.get("scanner_name") or "Burp Scanner issue").strip() or "Burp Scanner issue"
    host = str(event.get("host") or "")
    path = str(event.get("path") or "/")
    detail = _plain(str(event.get("scanner_detail") or ""))[:400]
    description = f"{name} on `{host}{path}`."
    if detail:
        description = f"{description} {detail}"
    return {
        "title": f"{name} on {host}"[:200],
        "description": description[:800],
        "impact": "",
        "evidence": _event_row_as_markdown(event),
        "remediation": "",
        "category_name": name,
    }


def propose_scanner(
    app_id: int,
    wave_id: int,
    username: str,
    role: str,
    data: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    access, status = get_wave(app_id, wave_id, username=username, role=role)
    if status != 200:
        return access, status
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    if not wave_is_open(wave):
        return {"error": "This wave has ended. Findings and wave details are read-only."}, 400
    try:
        event_id = int(data.get("event_id"))
    except (TypeError, ValueError):
        return {"error": "event_id is required."}, 400
    event = burp_repository.get_event(event_id, wave_id=wave_id)
    if not event:
        return {"error": "Burp event not found."}, 404
    if not str(event.get("scanner_name") or "").strip():
        return {"error": "This event is not a Burp Scanner issue."}, 400
    name = str(event.get("scanner_name") or "")
    host = str(event.get("host") or "")
    path = str(event.get("path") or "/")
    for row in burp_repository.list_proposals_for_wave(wave_id, kind="scanner"):
        if str(row.get("finding_id") or "").strip():
            continue
        if str(row.get("status") or "pending") != "pending":
            continue
        result = row.get("result_json") if isinstance(row.get("result_json"), dict) else {}
        if int(result.get("event_id") or 0) == int(event.get("id") or 0) or (
            str(result.get("scanner_name") or "") == name
            and str(result.get("host") or "") == host
            and str(result.get("path") or "") == path
        ):
            return {
                "proposal_id": int(row["id"]),
                "engagement_id": f"proposal:{row['id']}",
                "existing": True,
            }, 200
    writeup = scanner_writeup(event)
    proposal_id = burp_repository.insert_proposal(
        wave_id=int(wave_id),
        application_id=int(app_id),
        job_id=None,
        kind="scanner",
        title=writeup["title"],
        description=writeup["description"],
        result_json={
            "writeup": writeup,
            "event_id": event.get("id"),
            "host": host,
            "path": path,
            "scanner_name": name,
            "scanner_severity": event.get("scanner_severity") or "",
            "exchange": writeup["evidence"],
        },
    )
    return {
        "proposal_id": proposal_id,
        "engagement_id": f"proposal:{proposal_id}",
        "title": writeup["title"],
    }, 201


def accept_scanner_proposal(
    app_id: int,
    wave_id: int,
    proposal_id: int,
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
    proposal = burp_repository.get_proposal(int(proposal_id))
    if not proposal or int(proposal.get("wave_id") or 0) != int(wave_id):
        return {"error": "Proposal not found."}, 404
    if str(proposal.get("kind") or "") != "scanner":
        return {"error": "This proposal is not a Scanner issue."}, 400
    if proposal.get("finding_id"):
        return {"finding_id": proposal.get("finding_id"), "already_accepted": True}, 200
    result = proposal.get("result_json") if isinstance(proposal.get("result_json"), dict) else {}
    writeup = result.get("writeup") if isinstance(result.get("writeup"), dict) else {}
    host = str(result.get("host") or writeup.get("host") or "")
    record_id = record_id_for_host(wave, host)
    if not record_id:
        return {"error": "No in-scope host matches this proposal."}, 400
    title = str(writeup.get("title") or proposal.get("title") or "Burp Scanner issue")
    description = str(writeup.get("description") or proposal.get("description") or "")
    evidence = str(writeup.get("evidence") or result.get("exchange") or "")
    payload, created_status = create_finding(
        app_id,
        {
            "record_id": record_id,
            "wave_id": wave_id,
            "title": title,
            "description": description,
            "impact": str(writeup.get("impact") or ""),
            "evidence": evidence,
            "remediation": str(writeup.get("remediation") or ""),
            "category_name": str(writeup.get("category_name") or ""),
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
