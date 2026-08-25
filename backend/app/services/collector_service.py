import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.repositories.collector_repository import (
    consume_collect_request,
    delete_agent,
    get_agent_by_id,
    get_agent_by_token_hash,
    get_enroll_token_by_hash,
    insert_agent,
    insert_enroll_token,
    list_active_agents,
    list_agents,
    mark_collect_requested,
    mark_enroll_token_used,
    revoke_agent,
    rotate_agent_token,
    touch_agent_heartbeat,
    update_agent_fields,
)
from app.repositories.dns_sources_repository import BIND_AGENT_SOURCE_TYPE, create_dns_source
from app.services.audit_service import record_audit_event
from app.services.collector_dist import COLLECTOR_VERSION, version_payload
from app.services.ingest.apply import apply_ingest_batch

logger = logging.getLogger(__name__)

ENROLL_TOKEN_TTL = timedelta(hours=24)
AGENT_TOKEN_ROTATE_AFTER = timedelta(hours=24)
ENROLL_PREFIX = "raptor_enroll_"
AGENT_PREFIX = "raptor_col_"
ONE_SIDED = "one_sided"
TWO_SIDED = "two_sided"
DEFAULT_INTERVAL_SECONDS = 300
ONLINE_FALLBACK = timedelta(minutes=15)
MAX_INTERVAL_SECONDS = 7 * 24 * 3600


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _generate_token(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def _normalize_mode(raw: Any) -> str:
    value = str(raw or ONE_SIDED).strip().lower().replace("-", "_")
    if value in {"two_sided", "twosided", "bidirectional", "two_way"}:
        return TWO_SIDED
    return ONE_SIDED


def _normalize_interval(raw: Any) -> Optional[int]:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return max(30, min(value, MAX_INTERVAL_SECONDS))


def _live_window(interval_seconds: Any) -> timedelta:
    interval = _normalize_interval(interval_seconds)
    if not interval:
        return ONLINE_FALLBACK
    grace = max(60, int(interval * 0.2))
    return timedelta(seconds=interval + grace)


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


def _host_for_url(ip: str) -> str:
    value = str(ip or "").strip()
    if not value:
        return ""
    if ":" in value and not value.startswith("["):
        return f"[{value}]"
    return value


def _callback_port(callback: str) -> int:
    parsed = urlparse(callback)
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    return 7444


def _ping_urls(row: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    callback = str(row.get("callback_url") or "").strip().rstrip("/")
    parsed = urlparse(callback)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        urls.append(callback)
    ip = _host_for_url(str(row.get("last_seen_ip") or ""))
    if ip:
        fallback = f"http://{ip}:{_callback_port(callback)}"
        if fallback not in urls:
            urls.append(fallback)
    return urls


def _explain_ping_error(exc: Exception, url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or url
    port = parsed.port or (443 if parsed.scheme == "https" else 7444)
    text = str(exc)
    lowered = text.lower()
    if any(
        marker in lowered
        for marker in (
            "name or service not known",
            "nodename nor servname",
            "temporary failure in name resolution",
            "getaddrinfo failed",
            "name resolution",
        )
    ):
        return (
            f"RAPTOR cannot resolve hostname '{host}'. "
            "Two-sided ping needs a DNS name or IP that this RAPTOR server can reach. "
            "Set the callback URL to http://<reachable-ip>:7444, or put the agent on the same network."
        )
    if "connection refused" in lowered or "errno 111" in lowered:
        return (
            f"Reached {host} but nothing is listening on port {port}. "
            "Keep `raptor-collector run` running in two-sided mode."
        )
    if "timed out" in lowered or "timeout" in lowered:
        return (
            f"No response from {host}:{port} within 3s. "
            "Check firewalls, routing, and that the collector process is running."
        )
    return text


def _public_base(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _install_commands(base_url: str, token: str, name: str, mode: str) -> Dict[str, str]:
    base = _public_base(base_url) or "https://<raptor-host>"
    safe_name = name.replace('"', "").replace("'", "") or "dns-collector"
    linux = (
        f"curl -fsSL {base}/collector/v1/download/linux-amd64 -o raptor-collector "
        f"&& chmod +x raptor-collector "
        f"&& ./raptor-collector setup --url {base} --token {token} "
        f'--name "{safe_name}" --mode {mode.replace("_", "-")}'
    )
    windows = (
        f"Invoke-WebRequest -UseBasicParsing {base}/collector/v1/download/install.ps1 "
        f'-OutFile install-raptor-collector.ps1; '
        f'.\\install-raptor-collector.ps1 -Token "{token}" -Name "{safe_name}" '
        f'-Mode {mode.replace("_", "-")}'
    )
    return {"linux": linux, "windows": windows}


def _public_agent(row: Dict[str, Any]) -> Dict[str, Any]:
    interval = _normalize_interval(row.get("interval_seconds")) or DEFAULT_INTERVAL_SECONDS
    last_seen = _parse_ts(row.get("last_seen_at"))
    online = bool(last_seen and (_utc_now() - last_seen) <= _live_window(row.get("interval_seconds")))
    last_ingest = _parse_ts(row.get("last_ingest_at"))
    ingest_recent = bool(last_ingest and (_utc_now() - last_ingest) <= timedelta(seconds=90))
    display = str(row.get("display_name") or "").strip() or str(row.get("hostname") or "")
    return {
        "id": row.get("id"),
        "source_id": row.get("source_id"),
        "source_key": row.get("source_key"),
        "hostname": row.get("hostname"),
        "display_name": display,
        "agent_version": row.get("agent_version") or "",
        "status": row.get("status"),
        "mode": row.get("mode") or ONE_SIDED,
        "callback_url": row.get("callback_url") or "",
        "last_seen_ip": row.get("last_seen_ip") or "",
        "interval_seconds": interval,
        "collect_pending": bool(row.get("collect_requested_at")),
        "enrolled_at": str(row.get("enrolled_at") or ""),
        "last_seen_at": str(row.get("last_seen_at") or ""),
        "last_ingest_at": str(row.get("last_ingest_at") or ""),
        "last_soa_serial": row.get("last_soa_serial") or "",
        "last_zones": row.get("last_zones") or [],
        "last_success_at": str(row.get("last_success_at") or ""),
        "last_error": row.get("last_error"),
        "cursor": row.get("cursor") or "",
        "online": online,
        "ingesting": ingest_recent,
    }


def create_enroll_token_service(
    data: Dict[str, Any],
    actor_username: str,
    public_base_url: str = "",
) -> Tuple[Dict[str, Any], int]:
    label = str(data.get("label") or data.get("name") or "").strip() or "collector"
    mode = _normalize_mode(data.get("mode"))
    token = _generate_token(ENROLL_PREFIX)
    expires_at = (_utc_now() + ENROLL_TOKEN_TTL).replace(microsecond=0)
    token_id = insert_enroll_token(
        token_hash=_hash_token(token),
        label=label,
        created_by=actor_username,
        expires_at=expires_at.isoformat(),
    )
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="collector.enroll_token.create",
        entity_type="collector_enroll_token",
        entity_id=str(token_id),
        metadata={"label": label, "mode": mode},
    )
    commands = _install_commands(public_base_url, token, label, mode)
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "label": label,
        "mode": mode,
        "version": COLLECTOR_VERSION,
        "install": commands,
        "enroll_command": commands["linux"],
    }, 201


def list_collectors_service(
    limit: Any = 25,
    offset: Any = 0,
    query: str = "",
) -> Tuple[Dict[str, Any], int]:
    try:
        parsed_limit = min(100, max(1, int(limit)))
    except (TypeError, ValueError):
        parsed_limit = 25
    try:
        parsed_offset = max(0, int(offset))
    except (TypeError, ValueError):
        parsed_offset = 0
    rows, total = list_agents(limit=parsed_limit, offset=parsed_offset, query=str(query or ""))
    payload = version_payload()
    payload.update(
        {
            "agents": [_public_agent(row) for row in rows],
            "total": total,
            "limit": parsed_limit,
            "offset": parsed_offset,
        }
    )
    return payload, 200


def enroll_agent_service(data: Dict[str, Any], last_seen_ip: str = "") -> Tuple[Dict[str, Any], int]:
    bootstrap = str(data.get("token") or data.get("enroll_token") or "").strip()
    hostname = str(data.get("hostname") or "").strip().lower()
    display_name = str(data.get("display_name") or data.get("name") or hostname).strip()
    agent_version = str(data.get("agent_version") or "").strip()
    mode = _normalize_mode(data.get("mode"))
    callback_url = str(data.get("callback_url") or "").strip()
    if mode == TWO_SIDED and callback_url:
        parsed = urlparse(callback_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return {"error": "callback_url must be http(s) with a host."}, 400
    elif mode == TWO_SIDED:
        callback_url = ""
    if not bootstrap:
        return {"error": "Enroll token is required."}, 400
    if not hostname:
        return {"error": "hostname is required."}, 400

    token_row = get_enroll_token_by_hash(_hash_token(bootstrap))
    if not token_row:
        return {"error": "Invalid enroll token."}, 401
    if token_row.get("revoked_at"):
        return {"error": "Enroll token revoked."}, 401
    if token_row.get("used_at"):
        return {"error": "Enroll token already used."}, 401

    expires_at = token_row.get("expires_at")
    try:
        expiry = expires_at if isinstance(expires_at, datetime) else datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry < _utc_now():
            return {"error": "Enroll token expired."}, 401
    except (TypeError, ValueError):
        return {"error": "Enroll token expired."}, 401

    source_key = f"bind_agent:{hostname}:{uuid.uuid4().hex[:8]}"
    source_id = create_dns_source(
        key=source_key,
        source_type=BIND_AGENT_SOURCE_TYPE,
        display_name=display_name or hostname,
        config={"hostname": hostname, "agent_version": agent_version, "mode": mode},
    )
    agent_token = _generate_token(AGENT_PREFIX)
    agent_id = insert_agent(
        source_id=source_id,
        hostname=hostname,
        agent_version=agent_version,
        token_hash=_hash_token(agent_token),
        enroll_token_id=int(token_row["id"]),
        display_name=display_name or hostname,
        mode=mode,
        callback_url=callback_url,
        last_seen_ip=str(last_seen_ip or "").strip(),
        interval_seconds=_normalize_interval(data.get("interval_seconds")) or DEFAULT_INTERVAL_SECONDS,
    )
    mark_enroll_token_used(int(token_row["id"]))
    record_audit_event(
        actor=hostname,
        actor_type="collector",
        action="collector.enroll",
        entity_type="collector_agent",
        entity_id=str(agent_id),
        metadata={"source_id": source_id, "hostname": hostname, "mode": mode},
    )
    return {
        "agent_id": agent_id,
        "source_id": source_id,
        "source_key": source_key,
        "token": agent_token,
        "hostname": hostname,
        "display_name": display_name or hostname,
        "mode": mode,
    }, 201


def authenticate_collector_token(raw_token: str) -> Optional[Dict[str, Any]]:
    token = str(raw_token or "").strip()
    if not token:
        return None
    row = get_agent_by_token_hash(_hash_token(token))
    if not row or row.get("status") != "active":
        return None
    if not row.get("source_enabled"):
        return None
    return row


def _maybe_rotate_token(agent: Dict[str, Any]) -> Optional[str]:
    rotated_at = agent.get("token_rotated_at")
    should_rotate = True
    if rotated_at:
        try:
            parsed = rotated_at if isinstance(rotated_at, datetime) else datetime.fromisoformat(str(rotated_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            should_rotate = (_utc_now() - parsed) >= AGENT_TOKEN_ROTATE_AFTER
        except (TypeError, ValueError):
            should_rotate = True
    if not should_rotate:
        return None
    new_token = _generate_token(AGENT_PREFIX)
    rotate_agent_token(int(agent["id"]), _hash_token(new_token))
    return new_token


def heartbeat_service(
    agent: Dict[str, Any],
    data: Dict[str, Any],
    last_seen_ip: str = "",
) -> Tuple[Dict[str, Any], int]:
    zones = data.get("zones") if isinstance(data.get("zones"), list) else []
    normalized_zones: List[Dict[str, Any]] = []
    last_serial = str(data.get("soa_serial") or data.get("last_soa_serial") or "")
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        name = str(zone.get("name") or "").strip().lower().rstrip(".")
        serial = str(zone.get("soa_serial") or zone.get("serial") or "")
        if not name:
            continue
        normalized_zones.append({"name": name, "soa_serial": serial})
        if serial and not last_serial:
            last_serial = serial
    version = str(data.get("agent_version") or agent.get("agent_version") or "")
    mode = _normalize_mode(data.get("mode") or agent.get("mode"))
    callback_url = str(data.get("callback_url") if "callback_url" in data else agent.get("callback_url") or "")
    interval_seconds = _normalize_interval(data.get("interval_seconds"))
    touch_agent_heartbeat(
        int(agent["id"]),
        agent_version=version,
        last_soa_serial=last_serial or None,
        last_zones=normalized_zones,
        mode=mode,
        callback_url=callback_url,
        last_seen_ip=str(last_seen_ip or "").strip() or None,
        interval_seconds=interval_seconds,
    )
    payload: Dict[str, Any] = {
        "ok": True,
        "source_id": agent.get("source_id"),
        "agent_id": agent.get("id"),
    }
    if consume_collect_request(int(agent["id"])):
        payload["collect_now"] = True
    rotated = _maybe_rotate_token(agent)
    if rotated:
        payload["token"] = rotated
    return payload, 200


def ingest_service(
    agent: Dict[str, Any],
    data: Dict[str, Any],
    last_seen_ip: str = "",
) -> Tuple[Dict[str, Any], int]:
    source_id = int(agent["source_id"])
    claimed = data.get("source_id")
    if claimed not in (None, "", source_id, str(source_id)):
        return {"error": "source_id does not match this agent."}, 403

    records: List[Dict[str, Any]] = []
    zones = data.get("zones") if isinstance(data.get("zones"), list) else []
    last_serial = str(data.get("cursor") or data.get("soa_serial") or "")
    zone_summaries: List[Dict[str, Any]] = []
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        zone_name = str(zone.get("name") or "").strip().lower().rstrip(".")
        serial = str(zone.get("soa_serial") or zone.get("serial") or "")
        if serial:
            last_serial = last_serial or serial
        zone_summaries.append({"name": zone_name, "soa_serial": serial})
        for item in zone.get("records") or []:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row["zone"] = zone_name
            records.append(row)

    if not records and isinstance(data.get("records"), list):
        records = [item for item in data["records"] if isinstance(item, dict)]

    if not records:
        return {"error": "No records in ingest batch."}, 400

    try:
        result = apply_ingest_batch(
            source_id,
            records,
            cursor=last_serial or None,
        )
    except Exception as exc:
        logger.exception("Collector ingest failed for source %s", source_id)
        from app.repositories.dns_sources_repository import mark_source_error
        from app.services.notifications_service import notify_by_roles

        mark_source_error(source_id, str(exc))
        notify_by_roles(
            notification_type="zone_sync_failure",
            roles=["admin"],
            title="Collector ingest failed",
            message=f"Collector {agent.get('hostname')} ingest failed: {exc}",
            send_email_flag=True,
        )
        return {"error": "Ingest failed."}, 500

    touch_agent_heartbeat(
        int(agent["id"]),
        agent_version=str(data.get("agent_version") or agent.get("agent_version") or ""),
        last_soa_serial=last_serial or None,
        last_zones=zone_summaries,
        last_seen_ip=str(last_seen_ip or "").strip() or None,
        ingest=True,
    )
    record_audit_event(
        actor=str(agent.get("hostname") or "collector"),
        actor_type="collector",
        action="ingest.batch.complete",
        entity_type="dns_source",
        entity_id=str(source_id),
        metadata={
            "agent_id": agent.get("id"),
            "stored": result["stored"],
            "projected": result["projected"],
            "cursor": last_serial,
        },
    )
    payload: Dict[str, Any] = {
        "ok": True,
        "source_id": source_id,
        "stored": result["stored"],
        "projected": result["projected"],
        "batch_id": result["batch_id"],
    }
    rotated = _maybe_rotate_token(agent)
    if rotated:
        payload["token"] = rotated
    return payload, 200


def rename_collector_service(agent_id: int, data: Dict[str, Any], actor_username: str) -> Tuple[Dict[str, Any], int]:
    row = get_agent_by_id(agent_id)
    if not row:
        return {"error": "Collector not found."}, 404
    name = None
    if "display_name" in data or "name" in data:
        name = str(data.get("display_name") or data.get("name") or "").strip()
        if not name or len(name) > 120:
            return {"error": "display_name must be 1–120 characters."}, 400
    callback_url = None
    if "callback_url" in data:
        callback_url = str(data.get("callback_url") or "").strip()
        if callback_url:
            parsed = urlparse(callback_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return {"error": "callback_url must be http(s) with a host."}, 400
    if name is None and callback_url is None:
        return {"error": "Nothing to update."}, 400
    update_agent_fields(agent_id, display_name=name, callback_url=callback_url)
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="collector.update",
        entity_type="collector_agent",
        entity_id=str(agent_id),
        metadata={"display_name": name, "callback_url": callback_url},
    )
    updated = get_agent_by_id(agent_id) or row
    return {"agent": _public_agent(updated)}, 200


def revoke_collector_service(agent_id: int, actor_username: str) -> Tuple[Dict[str, Any], int]:
    row = get_agent_by_id(agent_id)
    if not row:
        return {"error": "Collector not found."}, 404
    if row.get("status") == "revoked":
        return {"message": "Collector already revoked."}, 200
    revoke_agent(agent_id)
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="collector.revoke",
        entity_type="collector_agent",
        entity_id=str(agent_id),
        metadata={"hostname": row.get("hostname"), "source_id": row.get("source_id")},
    )
    return {"message": "Collector revoked."}, 200


def delete_collector_service(agent_id: int, actor_username: str) -> Tuple[Dict[str, Any], int]:
    row = get_agent_by_id(agent_id)
    if not row:
        return {"error": "Collector not found."}, 404
    delete_agent(agent_id)
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="collector.delete",
        entity_type="collector_agent",
        entity_id=str(agent_id),
        metadata={"hostname": row.get("hostname"), "source_id": row.get("source_id")},
    )
    return {"message": "Collector deleted. Its key can no longer ingest."}, 200


def rotate_collector_service(agent_id: int, actor_username: str) -> Tuple[Dict[str, Any], int]:
    row = get_agent_by_id(agent_id)
    if not row or row.get("status") != "active":
        return {"error": "Collector not found."}, 404
    new_token = _generate_token(AGENT_PREFIX)
    rotate_agent_token(agent_id, _hash_token(new_token))
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="collector.token.rotate",
        entity_type="collector_agent",
        entity_id=str(agent_id),
    )
    return {"token": new_token, "agent_id": agent_id}, 200


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def ping_collector_service(agent_id: int) -> Tuple[Dict[str, Any], int]:
    row = get_agent_by_id(agent_id)
    if not row:
        return {"error": "Collector not found."}, 404
    if str(row.get("mode") or ONE_SIDED) != TWO_SIDED:
        return {"error": "This agent is one-sided. RAPTOR cannot contact it."}, 400
    urls = _ping_urls(row)
    if not urls:
        return {"error": "Agent has not published a callback URL or reachable IP yet."}, 400
    started = _utc_now()
    opener = build_opener(_NoRedirect)
    last_error = "Ping failed."
    last_url = urls[-1]
    for callback in urls:
        health = urljoin(callback + "/", "healthz")
        last_url = health
        request = Request(health, method="GET", headers={"Accept": "application/json"})
        try:
            with opener.open(request, timeout=3) as response:
                latency = int((_utc_now() - started).total_seconds() * 1000)
                return {
                    "ok": response.status == 200,
                    "status_code": response.status,
                    "latency_ms": latency,
                    "url": health,
                }, 200
        except Exception as exc:
            last_error = _explain_ping_error(exc, health)
    latency = int((_utc_now() - started).total_seconds() * 1000)
    return {"ok": False, "error": last_error, "latency_ms": latency, "url": last_url}, 200


def _notify_agent_run(row: Dict[str, Any]) -> Dict[str, Any]:
    if str(row.get("mode") or ONE_SIDED) != TWO_SIDED:
        return {"immediate": False, "reason": "one_sided"}
    urls = _ping_urls(row)
    if not urls:
        return {"immediate": False, "error": "Agent has not published a callback URL or reachable IP yet."}
    opener = build_opener(_NoRedirect)
    last_error = "Collect request failed."
    last_url = urls[-1]
    for callback in urls:
        run_url = urljoin(callback + "/", "run")
        last_url = run_url
        request = Request(
            run_url,
            data=b"{}",
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with opener.open(request, timeout=3) as response:
                return {
                    "immediate": response.status < 300,
                    "status_code": response.status,
                    "url": run_url,
                }
        except Exception as exc:
            last_error = _explain_ping_error(exc, run_url)
    return {"immediate": False, "error": last_error, "url": last_url}


def collect_now_service(agent_id: int, actor_username: str) -> Tuple[Dict[str, Any], int]:
    row = get_agent_by_id(agent_id)
    if not row:
        return {"error": "Collector not found."}, 404
    if row.get("status") != "active":
        return {"error": "Collector is not active."}, 400
    mark_collect_requested(agent_id)
    result = _notify_agent_run(row)
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="collector.collect_now",
        entity_type="collector_agent",
        entity_id=str(agent_id),
        metadata={"immediate": result.get("immediate"), "mode": row.get("mode")},
    )
    payload: Dict[str, Any] = {
        "ok": True,
        "queued": True,
        "agent_id": agent_id,
        "immediate": bool(result.get("immediate")),
    }
    if result.get("error"):
        payload["error"] = result["error"]
    if result.get("reason"):
        payload["reason"] = result["reason"]
    return payload, 200


def collect_now_all_service(actor_username: str) -> Tuple[Dict[str, Any], int]:
    rows = list_active_agents()
    mark_collect_requested()
    results = []
    immediate = 0
    queued = 0
    for row in rows:
        queued += 1
        notify = _notify_agent_run(row)
        if notify.get("immediate"):
            immediate += 1
        results.append(
            {
                "agent_id": row.get("id"),
                "display_name": row.get("display_name") or row.get("hostname"),
                "immediate": bool(notify.get("immediate")),
                "error": notify.get("error"),
                "reason": notify.get("reason"),
            }
        )
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="collector.collect_now_all",
        entity_type="collector_agent",
        entity_id="*",
        metadata={"queued": queued, "immediate": immediate},
    )
    return {
        "ok": True,
        "queued": queued,
        "immediate": immediate,
        "agents": results,
    }, 200


def refresh_domains_service(actor_username: str) -> Tuple[Dict[str, Any], int]:
    agents_payload, _status = collect_now_all_service(actor_username)
    from app.repositories.dns_sources_repository import CLOUD_SOURCE_TYPES, list_dns_sources
    from app.services.cloud_dns_service import enqueue_source_sync

    queued = []
    for source in list_dns_sources(types=list(CLOUD_SOURCE_TYPES), enabled_only=True, mask=True):
        queued.append(
            {
                "source_id": source.get("id"),
                "type": source.get("type"),
                "job_id": enqueue_source_sync(int(source["id"])),
            }
        )
    return {
        "ok": True,
        "agents": agents_payload,
        "cloud": queued,
    }, 200
