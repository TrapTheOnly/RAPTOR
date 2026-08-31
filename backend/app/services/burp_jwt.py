import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.domain.burp.fields import jwt_like, normalize_host
from app.repositories import burp_repository, environments_repository, phase2b_repository
from app.repositories.scanner_config_repository import get_scanner_config

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CORRECT_KEY_LONG = re.compile(r"\[\+\] CORRECT key found:\s*(.+)", re.I)
_CORRECT_KEY_SHORT = re.compile(r"\[\+\] (.+) is the CORRECT key!", re.I)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def suite_hits(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """Fileable JWT weaknesses only (offline-proven). Generated tokens are not hits."""
    if not isinstance(payload, dict):
        return []
    found: List[Dict[str, str]] = []
    seen = set()
    declared = payload.get("hits") if isinstance(payload.get("hits"), list) else []
    for item in declared:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        detail = str(item.get("detail") or "").strip()[:200]
        step = str(item.get("step") or kind)
        if kind != "weak_secret" or not detail:
            continue
        key = (kind, detail)
        if key in seen:
            continue
        seen.add(key)
        found.append({"step": step, "kind": kind, "detail": detail})
    suite = payload.get("suite") if isinstance(payload.get("suite"), list) else []
    for step in suite:
        if not isinstance(step, dict):
            continue
        name = str(step.get("step") or "")
        blob = _strip_ansi(f"{step.get('stdout') or ''}\n{step.get('stderr') or ''}")
        for pattern in (_CORRECT_KEY_LONG, _CORRECT_KEY_SHORT):
            match = pattern.search(blob)
            if not match:
                continue
            detail = match.group(1).strip()[:200]
            key = ("weak_secret", detail)
            if not detail or key in seen:
                continue
            seen.add(key)
            found.append({"step": name or "weak_secret", "kind": "weak_secret", "detail": detail})
    return found


def suite_ran(payload: Dict[str, Any]) -> bool:
    """jwt_tool exits 1 even after a successful run. Judge by output, not return code."""
    if not isinstance(payload, dict):
        return False
    if suite_hits(payload):
        return True
    suite = payload.get("suite") if isinstance(payload.get("suite"), list) else []
    for step in suite:
        if not isinstance(step, dict):
            continue
        if step.get("success") is True:
            return True
        blob = _strip_ansi(f"{step.get('stdout') or ''}\n{step.get('stderr') or ''}")
        if "Traceback (most recent call last)" in blob or "InvalidWriteError" in blob:
            continue
        if any(marker in blob for marker in ("Original JWT", "Decoded Token Values", "CORRECT key", "Exploit:")):
            return True
    return False


WEAK_HMAC_METRICS = {
    "AV": "N",
    "AC": "L",
    "PR": "N",
    "UI": "N",
    "S": "U",
    "C": "H",
    "I": "H",
    "A": "N",
}


def _http_exchange_for_job(job: Optional[Dict[str, Any]]) -> str:
    if not isinstance(job, dict) or not job.get("wave_id"):
        return ""
    event = burp_repository.latest_http_event(
        int(job["wave_id"]),
        str(job.get("host") or ""),
        str(job.get("path") or ""),
    )
    if not event:
        return ""
    from app.services.http_evidence import markdown_from_event

    return markdown_from_event(event)


def finding_writeup(
    *,
    host: str,
    path: str,
    hits: List[Dict[str, str]],
    suite: Optional[List[Dict[str, Any]]] = None,
    screenshots: Optional[List[Dict[str, str]]] = None,
    http_exchange: str = "",
) -> Dict[str, Any]:
    """Finding fields for Accept. Evidence is payload then proof, no section headers."""
    from app.services.terminal_shot import (
        JWT_TOOL_COMMANDS,
        command_for_step,
        evidence_steps,
        markdown_excerpt,
    )

    target = normalize_host(host) or "the host"
    location = f"{target}{path or '/'}"
    secret = next(
        (str(item.get("detail") or "").strip() for item in hits if item.get("kind") == "weak_secret"),
        "",
    )
    secret_clause = f" HMAC secret `{secret}` is on a public wordlist." if secret else ""
    steps = evidence_steps(suite or [], hits)
    shots = [item for item in (screenshots or []) if isinstance(item, dict) and item.get("url")]
    shots_by_step: Dict[str, List[Dict[str, str]]] = {}
    for shot in shots:
        shots_by_step.setdefault(str(shot.get("step") or ""), []).append(shot)

    lines: List[str] = []
    exchange = str(http_exchange or "").strip()
    if exchange:
        lines.extend([exchange, ""])

    used_urls = set()
    shown_commands: List[str] = []
    for step in steps:
        cmd = command_for_step(step)
        if cmd not in shown_commands:
            shown_commands.append(cmd)
            lines.extend(["```shell", cmd, "```", ""])
        name = str(step.get("step") or "")
        matched = shots_by_step.get(name) or []
        if matched:
            for shot in matched:
                url = str(shot.get("url") or "")
                if not url or url in used_urls:
                    continue
                used_urls.add(url)
                alt = str(shot.get("alt") or name or "jwt_tool")
                lines.extend([f"![{alt}]({url})", ""])
        else:
            excerpt = markdown_excerpt(str(step.get("stdout") or ""), max_lines=16)
            if excerpt:
                lines.extend(["```", excerpt, "```", ""])

    if not shown_commands:
        lines.extend(["```shell", JWT_TOOL_COMMANDS["weak_secret"], "```", ""])
    for shot in shots:
        url = str(shot.get("url") or "")
        if not url or url in used_urls:
            continue
        alt = str(shot.get("alt") or shot.get("step") or "jwt_tool")
        lines.extend([f"![{alt}]({url})", ""])

    return {
        "title": f"Weak JWT HMAC secret on {target}",
        "description": (
            f"JWT at `{location}` verifies HS256 with a guessable secret."
            f"{secret_clause} Tokens can be forged; this was an offline crack only."
        ),
        "impact": (
            "Forged JWTs impersonate any user the application trusts, including admin."
        ),
        "evidence": "\n".join(line for line in lines).strip() + "\n",
        "remediation": (
            "Rotate to a long random HMAC secret or switch to RS256/ES256. "
            "Invalidate outstanding tokens after rotation. Keep the signing key off wordlists."
        ),
        "category_name": "Broken Authentication",
        "metrics": dict(WEAK_HMAC_METRICS),
        "base_score": 9.1,
    }


def _kali_url() -> str:
    return str(os.getenv("KALI_SERVER_URL") or "http://kali:5000").rstrip("/")


def _kali_headers(destructive: bool) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    token = str(os.getenv("KALI_INTERNAL_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if destructive:
        headers["X-Kali-Destructive"] = "1"
    return headers


def destructive_allowed(wave: Dict[str, Any], host: str) -> Tuple[bool, str]:
    cfg = get_scanner_config() or {}
    global_flag = bool(int(cfg.get("allow_destructive_tools") or 0))
    if not global_flag:
        return False, "Global scanner destructive tools are disabled."
    hosts = phase2b_repository.list_live_wave_hosts(wave)
    target = normalize_host(host)
    env_id = None
    for row in hosts:
        name = normalize_host(str(row.get("name") or ""))
        if name == target or (target and name.endswith("." + target)):
            env_id = row.get("environment_id")
            break
    if env_id is None and hosts:
        env_id = hosts[0].get("environment_id")
    if not env_id:
        return False, "Host is not in this wave."
    env = environments_repository.fetch_environment(int(wave["application_id"]), int(env_id)) or {}
    if not bool(int(env.get("allow_destructive") or 0)):
        return False, "This environment does not allow destructive tools."
    return True, ""


def _call_kali(token: str, host: str, path: str) -> Dict[str, Any]:
    url = f"{_kali_url()}/api/tools/jwt"
    try:
        response = httpx.post(
            url,
            json={"token": token, "host": host, "path": path},
            headers=_kali_headers(True),
            timeout=180.0,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return {"error": "Kali returned a non-object JWT result.", "success": False}
        return payload
    except httpx.HTTPError as exc:
        logger.warning("Kali jwt_attacks failed: %s", exc)
        return {"error": str(exc), "success": False}


def _name_job(job: Dict[str, Any], wave: Dict[str, Any]) -> str:
    from app.services.engagement_namer import app_and_wave_names, fallback_title, name_engagement

    kind = str(job.get("kind") or "jwt")
    host = str(job.get("host") or "")
    path = str(job.get("path") or "")
    try:
        burp_repository.update_job(int(job["id"]), status="naming")
        names = app_and_wave_names(wave)
        title = name_engagement(
            kind=kind,
            host=host,
            path=path,
            wave_name=names["wave_name"],
            app_name=names["app_name"],
        )
    except Exception as exc:
        logger.info("JWT job naming fell back: %s", exc)
        title = fallback_title(kind=kind, host=host, path=path, wave_name=str((wave or {}).get("name") or ""))
    burp_repository.update_job(int(job["id"]), status="pending", title=title)
    return title


def run_jwt_job(job_id: int) -> Dict[str, Any]:
    job = burp_repository.get_job(int(job_id))
    if not job:
        return {"error": "JWT job not found."}
    wave = phase2b_repository.get_wave(int(job["wave_id"]))
    if not wave:
        burp_repository.update_job(int(job_id), status="failed", error="Wave not found.")
        return {"error": "Wave not found."}
    _name_job(job, wave)
    allowed, reason = destructive_allowed(wave, str(job.get("host") or ""))
    if not allowed:
        burp_repository.update_job(int(job_id), status="failed", error=reason)
        return {"error": reason}
    payload = job.get("payload_json") if isinstance(job.get("payload_json"), dict) else {}
    token = jwt_like(str(payload.get("jwt") or payload.get("token") or "")) or ""
    if not token:
        burp_repository.update_job(int(job_id), status="failed", error="JWT is required.")
        return {"error": "JWT is required."}
    burp_repository.update_job(int(job_id), status="running")
    result = dict(_call_kali(token, str(job.get("host") or ""), str(job.get("path") or "")))
    hits = suite_hits(result)
    result["hits"] = hits
    ran = suite_ran(result)
    if not ran:
        error = str(result.get("error") or "jwt_tool did not run.")
        burp_repository.update_job(int(job_id), status="failed", result_json=result, error=error)
        return result
    if not hits:
        burp_repository.update_job(
            int(job_id),
            status="completed",
            result_json={"proposal_id": None, "kali": result},
        )
        return {"job_id": int(job_id), "proposal_id": None, "status": "completed"}
    from app.services.burp_hacktricks import search_hacktricks

    writeup = finding_writeup(
        host=str(job.get("host") or ""),
        path=str(job.get("path") or ""),
        hits=hits,
        http_exchange=_http_exchange_for_job(job),
    )
    result["hacktricks"] = search_hacktricks("jwt weak hmac secret", limit=3)
    result["writeup"] = writeup
    proposal_id = burp_repository.insert_proposal(
        wave_id=int(job["wave_id"]),
        application_id=int(job["application_id"]),
        job_id=int(job_id),
        kind="jwt",
        title=writeup["title"],
        description=writeup["description"],
        result_json=result,
    )
    burp_repository.update_job(
        int(job_id),
        status="completed",
        result_json={"proposal_id": proposal_id, "kali": result},
    )
    return {"job_id": int(job_id), "proposal_id": proposal_id, "status": "completed"}


def refresh_finding_evidence(finding_id: str) -> Dict[str, Any]:
    """Rebuild evidence markdown and freeze screenshots for an already-filed JWT finding."""
    from app.repositories.pentest_findings_repository import update_finding_fields
    from app.services.terminal_shot import attach_jwt_screenshots

    proposal = burp_repository.get_proposal_for_finding(str(finding_id or "").strip())
    if not proposal:
        return {"error": "No JWT proposal is linked to this finding."}
    job = burp_repository.get_job(int(proposal["job_id"])) if proposal.get("job_id") else None
    result = proposal.get("result_json") if isinstance(proposal.get("result_json"), dict) else {}
    hits = suite_hits(result)
    if not hits:
        return {"error": "This suite found no JWT weakness to file."}
    suite = result.get("suite") if isinstance(result.get("suite"), list) else []
    screenshots = attach_jwt_screenshots(suite, hits)
    writeup = finding_writeup(
        host=str((job or {}).get("host") or result.get("host") or ""),
        path=str((job or {}).get("path") or result.get("path") or ""),
        hits=hits,
        suite=suite,
        screenshots=screenshots,
        http_exchange=_http_exchange_for_job(job),
    )
    updated = update_finding_fields(
        str(finding_id),
        {
            "title": writeup["title"],
            "description": writeup["description"],
            "impact": writeup["impact"],
            "evidence": writeup["evidence"],
            "remediation": writeup["remediation"],
        },
    )
    if not updated:
        return {"error": "Finding not found."}
    return {"finding_id": str(finding_id), "screenshots": screenshots, "evidence": writeup["evidence"]}


def queue_jwt_job(
    *,
    wave: Dict[str, Any],
    agent_id: Optional[int],
    host: str,
    path: str,
    token: str,
) -> Tuple[Dict[str, Any], int]:
    allowed, reason = destructive_allowed(wave, host)
    if not allowed:
        return {"error": reason}, 403
    jwt = jwt_like(token)
    if not jwt:
        return {"error": "A JWT is required."}, 400
    job_id = burp_repository.insert_job(
        wave_id=int(wave["id"]),
        application_id=int(wave["application_id"]),
        agent_id=agent_id,
        kind="jwt",
        host=normalize_host(host),
        path=path or "/",
        payload_json={"jwt": jwt},
    )
    from app.repositories.jobs_repository import enqueue_job

    enqueue_job("burp_jwt", {"burp_job_id": job_id})
    return {"job_id": job_id, "status": "queued"}, 202
