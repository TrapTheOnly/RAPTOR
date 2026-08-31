import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.domain.burp.fields import (
    AGENT_PREFIX,
    ENROLL_PREFIX,
    MAX_INGEST_EVENTS,
    cap_body,
    cap_payload,
    dedupe_key,
    hash_token,
    is_static_path,
    jwt_like,
    jwt_present_in,
    normalize_host,
    normalize_path,
    redact_headers,
    strip_jwts,
)
from app.integrations.secrets import encrypt_secret
from app.repositories import burp_repository, phase2b_repository
from app.services import burp_index, burp_jwt
from app.services.audit_service import record_audit_event
from app.services.burp_dist import jar_path, version_payload
from app.services.phase2b_service import _is_override, reject_if_closed, wave_is_open

logger = logging.getLogger(__name__)

ENROLL_TOKEN_TTL = timedelta(hours=24)
AGENT_TOKEN_ROTATE_AFTER = timedelta(hours=24)
ALLOWED_TOOLS = {"repeater", "intruder", "scanner"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_token(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def peer_ip_from_request(forwarded_for: str = "", remote_addr: str = "") -> str:
    forwarded = str(forwarded_for or "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return str(remote_addr or "").strip()


def _wave_or_404(app_id: int, wave_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[Dict[str, Any], int]]]:
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return None, ({"error": "Wave not found."}, 404)
    return wave, None


def tester_can_mint(wave: Dict[str, Any], username: str, role: str) -> bool:
    if _is_override(role):
        return True
    actor = str(username or "").strip()
    if not actor:
        return False
    members = [str(item).strip() for item in (wave.get("members") or [])]
    return actor == str(wave.get("opened_by") or "").strip() or actor in members


def mint_wave_token(
    app_id: int,
    wave_id: int,
    username: str,
    role: str,
) -> Tuple[Dict[str, Any], int]:
    wave, error = _wave_or_404(app_id, wave_id)
    if error:
        return error
    closed = reject_if_closed(wave)
    if closed:
        return closed
    if not tester_can_mint(wave, username, role):
        return {"error": "Only testers on this wave can mint a Burp token."}, 403
    token = _generate_token(ENROLL_PREFIX)
    expires_at = (_utc_now() + ENROLL_TOKEN_TTL).replace(microsecond=0)
    burp_repository.revoke_wave_enroll_tokens(wave_id)
    token_id = burp_repository.insert_enroll_token(
        wave_id=wave_id,
        application_id=app_id,
        token_hash=hash_token(token),
        created_by=username,
        expires_at=expires_at.isoformat(),
    )
    record_audit_event(
        actor=username or "tester",
        actor_type="user",
        action="burp.enroll_token.create",
        entity_type="burp_enroll_token",
        entity_id=str(token_id),
        metadata={"wave_id": wave_id},
    )
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "wave_id": wave_id,
        "jar": version_payload(),
    }, 201


def revoke_wave_token(app_id: int, wave_id: int, username: str, role: str) -> Tuple[Dict[str, Any], int]:
    wave, error = _wave_or_404(app_id, wave_id)
    if error:
        return error
    if not tester_can_mint(wave, username, role):
        return {"error": "Only testers on this wave can revoke a Burp token."}, 403
    tokens = burp_repository.revoke_wave_enroll_tokens(wave_id)
    agents = burp_repository.revoke_wave_agents(wave_id)
    record_audit_event(
        actor=username or "tester",
        actor_type="user",
        action="burp.revoke",
        entity_type="engagement_wave",
        entity_id=str(wave_id),
        metadata={"tokens": tokens, "agents": agents},
    )
    return {"revoked_tokens": tokens, "revoked_agents": agents}, 200


def wave_burp_status(app_id: int, wave_id: int) -> Tuple[Dict[str, Any], int]:
    wave, error = _wave_or_404(app_id, wave_id)
    if error:
        return error
    enroll = burp_repository.latest_enroll_token(wave_id)
    agents = burp_repository.list_agents_for_wave(wave_id)
    enroll_public = None
    if enroll:
        enroll_public = {
            "issued": True,
            "expires_at": str(enroll.get("expires_at") or ""),
            "used": bool(enroll.get("used_at")),
            "revoked": bool(enroll.get("revoked_at")),
            "created_by": enroll.get("created_by") or "",
        }
    return {
        "wave_id": wave_id,
        "jar": version_payload(),
        "enroll": enroll_public,
        "agents": [
            {
                "id": row.get("id"),
                "hostname": row.get("hostname") or "",
                "username": row.get("username") or "",
                "burp_version": row.get("burp_version") or "",
                "status": row.get("status") or "",
                "last_heartbeat_at": str(row.get("last_heartbeat_at") or ""),
                "started_at": str(row.get("started_at") or ""),
            }
            for row in agents
        ],
        "event_count": burp_repository.count_events(wave_id),
        "wave_open": wave_is_open(wave),
    }, 200


def authenticate_burp_token(raw_token: str) -> Optional[Dict[str, Any]]:
    token = str(raw_token or "").strip()
    if not token:
        return None
    row = burp_repository.get_agent_by_token_hash(hash_token(token))
    if not row or row.get("status") != "active":
        return None
    return row


def enroll_agent_service(data: Dict[str, Any], last_seen_ip: str = "") -> Tuple[Dict[str, Any], int]:
    bootstrap = str(data.get("token") or data.get("enroll_token") or "").strip()
    hostname = str(data.get("hostname") or "").strip().lower()
    burp_version = str(data.get("burp_version") or data.get("agent_version") or "").strip()
    if not bootstrap:
        return {"error": "Enroll token is required."}, 400
    if not hostname:
        return {"error": "hostname is required."}, 400
    token_row = burp_repository.get_enroll_token_by_hash(hash_token(bootstrap))
    if not token_row:
        return {"error": "Invalid enroll token."}, 401
    if token_row.get("revoked_at"):
        return {"error": "Enroll token revoked."}, 401
    if token_row.get("used_at"):
        return {"error": "Enroll token already used."}, 401
    expires_at = _parse_ts(token_row.get("expires_at"))
    if not expires_at or expires_at < _utc_now():
        return {"error": "Enroll token expired."}, 401
    wave = phase2b_repository.get_wave(int(token_row["wave_id"]))
    closed = reject_if_closed(wave)
    if closed:
        return closed
    agent_token = _generate_token(AGENT_PREFIX)
    agent_id = burp_repository.insert_agent(
        wave_id=int(token_row["wave_id"]),
        application_id=int(token_row["application_id"]),
        enroll_token_id=int(token_row["id"]),
        username=str(token_row.get("created_by") or ""),
        hostname=hostname,
        burp_version=burp_version,
        token_hash=hash_token(agent_token),
        last_seen_ip=str(last_seen_ip or "").strip(),
    )
    burp_repository.mark_enroll_token_used(int(token_row["id"]))
    record_audit_event(
        actor=hostname,
        actor_type="burp",
        action="burp.enroll",
        entity_type="burp_agent",
        entity_id=str(agent_id),
        metadata={"wave_id": token_row["wave_id"], "hostname": hostname},
    )
    return {
        "agent_id": agent_id,
        "wave_id": int(token_row["wave_id"]),
        "wave_name": str((wave or {}).get("name") or ""),
        "token": agent_token,
        "hostname": hostname,
    }, 201


def _maybe_rotate_token(agent: Dict[str, Any]) -> Optional[str]:
    rotated_at = _parse_ts(agent.get("token_rotated_at"))
    if rotated_at and (_utc_now() - rotated_at) < AGENT_TOKEN_ROTATE_AFTER:
        return None
    new_token = _generate_token(AGENT_PREFIX)
    burp_repository.rotate_agent_token(int(agent["id"]), hash_token(new_token))
    return new_token


def _in_scope_hosts(wave: Dict[str, Any]) -> List[str]:
    hosts = []
    for row in phase2b_repository.list_live_wave_hosts(wave):
        if row.get("in_scope") is False:
            continue
        name = normalize_host(str(row.get("name") or ""))
        if name:
            hosts.append(name)
    return hosts


def host_in_scope(wave: Dict[str, Any], host: str) -> bool:
    target = normalize_host(host)
    if not target:
        return False
    for name in _in_scope_hosts(wave):
        if target == name or target.endswith("." + name) or name.endswith("." + target):
            return True
    return False


def record_id_for_host(wave: Dict[str, Any], host: str) -> Optional[int]:
    target = normalize_host(host)
    if not target:
        return None
    for row in phase2b_repository.list_live_wave_hosts(wave):
        name = normalize_host(str(row.get("name") or ""))
        if not name:
            continue
        if target == name or target.endswith("." + name) or name.endswith("." + target):
            try:
                return int(row["id"])
            except (TypeError, ValueError, KeyError):
                return None
    return None


def heartbeat_service(agent: Dict[str, Any], data: Dict[str, Any], last_seen_ip: str = "") -> Tuple[Dict[str, Any], int]:
    wave = phase2b_repository.get_wave(int(agent["wave_id"]))
    closed = reject_if_closed(wave)
    if closed:
        return closed
    burp_repository.touch_agent_heartbeat(
        int(agent["id"]),
        burp_version=str(data.get("burp_version") or ""),
        last_seen_ip=str(last_seen_ip or "").strip(),
    )
    payload: Dict[str, Any] = {
        "ok": True,
        "wave_id": int(agent["wave_id"]),
        "wave_name": str((wave or {}).get("name") or ""),
        "hosts": _in_scope_hosts(wave or {}),
        "heartbeat_interval_seconds": 60,
    }
    rotated = _maybe_rotate_token(agent)
    if rotated:
        payload["token"] = rotated
    return payload, 200


def _header_blob(headers: Any) -> str:
    if isinstance(headers, dict):
        return " ".join(str(value or "") for value in headers.values())
    if isinstance(headers, list):
        parts = []
        for entry in headers:
            if isinstance(entry, dict):
                parts.append(str(entry.get("value") or ""))
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                parts.append(str(entry[1] or ""))
        return " ".join(parts)
    return ""


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _normalize_event(raw: Any, *, allow_static: bool = False) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    tool = str(raw.get("tool") or "").strip().lower()
    if tool not in ALLOWED_TOOLS:
        return None
    host = normalize_host(str(raw.get("host") or ""))
    path = normalize_path(str(raw.get("path") or "/"))
    method = str(raw.get("method") or "GET").strip().upper() or "GET"
    if not host:
        return None
    if tool != "scanner" and is_static_path(path) and not allow_static:
        return None
    raw_body = str(raw.get("body") or raw.get("normalized_body") or "")
    raw_response = str(raw.get("response_body") or "")
    query = strip_jwts(str(raw.get("query") or ""))
    body = strip_jwts(cap_body(raw_body))
    response_body = strip_jwts(cap_body(raw_response))
    key = str(raw.get("dedupe_key") or "").strip() or dedupe_key(tool, method, host, path, body)
    status = raw.get("status")
    try:
        status_i = int(status) if status is not None and str(status) != "" else None
    except (TypeError, ValueError):
        status_i = None
    jwt_present = _truthy(raw.get("jwt_present")) or jwt_present_in(
        raw_body,
        raw_response,
        raw.get("query") or "",
        _header_blob(raw.get("headers")),
        _header_blob(raw.get("response_headers")),
        raw.get("jwt") or raw.get("token") or "",
    )
    excerpt = {
        "headers": redact_headers(raw.get("headers") or {}),
        "body": body,
        "query": query,
        "length": raw.get("length"),
        "response_headers": redact_headers(raw.get("response_headers") or {}),
        "response_body": response_body,
        "payload": cap_payload(raw.get("payload") or ""),
        "jwt_present": jwt_present,
    }
    return {
        "tool": tool,
        "dedupe_key": key,
        "host": host,
        "path": path,
        "method": method,
        "status": status_i,
        "excerpt_json": excerpt,
        "scanner_type": str(raw.get("scanner_type") or raw.get("type") or ""),
        "scanner_name": str(raw.get("scanner_name") or raw.get("name") or raw.get("issue_name") or ""),
        "scanner_severity": str(raw.get("severity") or raw.get("scanner_severity") or ""),
        "scanner_confidence": str(raw.get("confidence") or raw.get("scanner_confidence") or ""),
        "scanner_parameter": str(raw.get("parameter") or raw.get("scanner_parameter") or ""),
        "scanner_detail": str(raw.get("detail") or raw.get("scanner_detail") or "")[:2000],
    }


def ingest_service(agent: Dict[str, Any], data: Dict[str, Any], last_seen_ip: str = "") -> Tuple[Dict[str, Any], int]:
    wave = phase2b_repository.get_wave(int(agent["wave_id"]))
    closed = reject_if_closed(wave)
    if closed:
        return closed
    events = data.get("events") if isinstance(data.get("events"), list) else []
    if len(events) > MAX_INGEST_EVENTS:
        return {"error": f"At most {MAX_INGEST_EVENTS} events per POST."}, 400
    accepted = 0
    skipped = 0
    last_row = None
    for raw in events:
        event = _normalize_event(raw)
        if not event:
            skipped += 1
            continue
        if not host_in_scope(wave or {}, event["host"]):
            skipped += 1
            continue
        last_row = burp_repository.upsert_event(
            wave_id=int(agent["wave_id"]),
            application_id=int(agent["application_id"]),
            agent_id=int(agent["id"]),
            **event,
        )
        accepted += 1
    if accepted:
        burp_index.rewrite_index(int(agent["wave_id"]))
        burp_repository.touch_agent_heartbeat(
            int(agent["id"]),
            last_seen_ip=str(last_seen_ip or "").strip(),
        )
    return {
        "accepted": accepted,
        "skipped": skipped,
        "last_event_id": (last_row or {}).get("id"),
        "last_count": (last_row or {}).get("count"),
    }, 200


def store_auth_template(agent: Dict[str, Any], data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    wave = phase2b_repository.get_wave(int(agent["wave_id"]))
    closed = reject_if_closed(wave)
    if closed:
        return closed
    raw_request = str(data.get("raw_request") or data.get("request") or "").strip()
    host = normalize_host(str(data.get("host") or ""))
    if not raw_request or not host:
        return {"error": "host and raw_request are required."}, 400
    if not host_in_scope(wave or {}, host):
        return {"error": "Host is out of wave scope."}, 400
    placeholder_map = data.get("placeholder_map") if isinstance(data.get("placeholder_map"), dict) else {}
    extract_rule = data.get("extract_rule") if isinstance(data.get("extract_rule"), dict) else {}
    template_id = burp_repository.upsert_auth_template(
        wave_id=int(agent["wave_id"]),
        application_id=int(agent["application_id"]),
        agent_id=int(agent["id"]),
        host=host,
        method=str(data.get("method") or "POST").strip().upper() or "POST",
        path=normalize_path(str(data.get("path") or "/")),
        request_ciphertext=encrypt_secret(raw_request),
        placeholder_map=placeholder_map,
        extract_rule=extract_rule,
        created_by=str(agent.get("username") or ""),
    )
    record_audit_event(
        actor=str(agent.get("hostname") or "burp"),
        actor_type="burp",
        action="burp.auth_template",
        entity_type="burp_auth_template",
        entity_id=str(template_id),
        metadata={"wave_id": agent["wave_id"], "host": host},
    )
    return {"id": template_id, "host": host}, 201


def enqueue_jwt(agent: Dict[str, Any], data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    wave = phase2b_repository.get_wave(int(agent["wave_id"]))
    closed = reject_if_closed(wave)
    if closed:
        return closed
    host = normalize_host(str(data.get("host") or ""))
    if not host_in_scope(wave or {}, host):
        return {"error": "Host is out of wave scope."}, 400
    token = jwt_like(str(data.get("jwt") or data.get("token") or "")) or ""
    return burp_jwt.queue_jwt_job(
        wave=wave or {},
        agent_id=int(agent["id"]),
        host=host,
        path=normalize_path(str(data.get("path") or "/")),
        token=token,
    )


def download_jar():
    path = jar_path()
    if not path:
        return None
    return path
