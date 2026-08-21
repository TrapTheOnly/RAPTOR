"""Pull DNS connectors: sync jobs and admin CRUD."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.dns_sources_repository import (
    CLOUD_SOURCE_TYPES,
    PULL_SOURCE_TYPES,
    create_dns_source,
    delete_dns_source,
    get_dns_source,
    list_dns_sources,
    list_zones_for_source,
    mark_source_error,
    update_dns_source,
)
from app.repositories.jobs_repository import enqueue_job, has_pending_or_running
from app.services.audit_service import record_audit_event
from app.services.ingest.apply import apply_ingest_batch
from app.services.ingest.connectors.registry import build_connector, fetch_all_records
from app.services.ingest.secrets import MASK

logger = logging.getLogger(__name__)

TYPE_LABELS = {
    "cloudflare": "Cloudflare",
    "route53": "Amazon Route 53",
    "alidns": "Alibaba Cloud DNS",
    "azure": "Azure DNS",
    "gcp": "Google Cloud DNS",
}


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        stamp = value
        if stamp.tzinfo is None:
            return stamp.replace(tzinfo=timezone.utc)
        return stamp
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def source_interval_seconds(source: Dict[str, Any]) -> int:
    config = source.get("config") if isinstance(source.get("config"), dict) else {}
    raw = config.get("interval_seconds")
    default = 3600
    try:
        return max(60, int(raw if raw not in (None, "") else default))
    except (TypeError, ValueError):
        return default


def source_due_for_sync(source: Dict[str, Any], *, force: bool = False) -> bool:
    if force:
        return True
    last = _parse_timestamp(source.get("last_success_at"))
    if last is None:
        return True
    now = datetime.now(timezone.utc)
    elapsed = (now - last.astimezone(timezone.utc)).total_seconds()
    return elapsed >= source_interval_seconds(source)


def cursor_from_records(records: List[Any]) -> str:
    zones = sorted({str(getattr(item, "zone", "") or "") for item in records if getattr(item, "zone", "")})
    count = len(records)
    return f"{count}:{','.join(zones[:12])}"


def sync_pull_source(source_id: int, *, force: bool = True) -> Dict[str, Any]:
    source = get_dns_source(source_id, decrypt=True, mask=False)
    if not source:
        return {"ok": True, "skipped": True, "reason": "deleted"}
    if source.get("type") not in PULL_SOURCE_TYPES:
        raise RuntimeError("This DNS source is push-only.")
    if not source.get("enabled"):
        return {"ok": True, "skipped": True, "reason": "disabled"}
    if not source_due_for_sync(source, force=force):
        return {"ok": True, "skipped": True, "reason": "interval"}

    connector = build_connector(str(source.get("type")), source.get("config") or {})
    records = fetch_all_records(connector)

    result = apply_ingest_batch(
        int(source["id"]),
        records,
        cursor=cursor_from_records(records),
    )
    record_audit_event(
        actor="system",
        actor_type="worker",
        action="ingest.dns_sync",
        entity_type="dns_source",
        entity_id=str(source.get("key") or source_id),
        metadata={
            "source_id": source_id,
            "type": source.get("type"),
            "stored": result.get("stored"),
            "projected": result.get("projected"),
        },
    )
    return {"ok": True, "skipped": False, **result}


def sync_all_pull_sources(*, force: bool = False) -> Dict[str, Any]:
    sources = list_dns_sources(types=list(PULL_SOURCE_TYPES), enabled_only=True, decrypt=True, mask=False)
    results = []
    errors = 0
    for source in sources:
        try:
            results.append(
                {
                    "source_id": source.get("id"),
                    "type": source.get("type"),
                    **sync_pull_source(int(source["id"]), force=force),
                }
            )
        except Exception as exc:
            errors += 1
            logger.exception("DNS pull failed for source %s", source.get("id"))
            mark_source_error(int(source["id"]), str(exc))
            try:
                from app.services.notifications_service import notify_by_roles

                notify_by_roles(
                    notification_type="zone_sync_failure",
                    roles=["admin"],
                    title="DNS connector sync failed",
                    message=f"{source.get('display_name') or source.get('type')} failed: {exc}",
                    send_email_flag=True,
                )
            except Exception:
                pass
            results.append(
                {
                    "source_id": source.get("id"),
                    "type": source.get("type"),
                    "ok": False,
                    "error": str(exc),
                }
            )
    return {"ok": errors == 0, "results": results}


def enqueue_source_sync(source_id: Optional[int] = None) -> int:
    payload = {"source_id": int(source_id)} if source_id else {}
    kind = "dns_sync"
    if source_id is None and has_pending_or_running(kind):
        return 0
    return enqueue_job(kind, payload)


def list_cloud_sources_service() -> Tuple[Dict[str, Any], int]:
    rows = list_dns_sources(types=list(CLOUD_SOURCE_TYPES), mask=True)
    for row in rows:
        row["type_label"] = TYPE_LABELS.get(row.get("type"), row.get("type"))
        row["zone_count"] = len(list_zones_for_source(int(row["id"])))
    return {"sources": rows}, 200


def _normalize_provider_config(source_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(config)
    if source_type != "gcp":
        return out
    raw = out.get("service_account_json")
    parsed = None
    if isinstance(raw, dict):
        parsed = raw
        out["service_account_json"] = json.dumps(raw)
    elif isinstance(raw, str) and raw.strip() and raw != MASK:
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, dict):
            parsed = loaded
    if parsed:
        out["project_id"] = str(out.get("project_id") or parsed.get("project_id") or "").strip()
        out["client_email"] = str(out.get("client_email") or parsed.get("client_email") or "").strip()
        if parsed.get("private_key") and not out.get("private_key"):
            out["private_key"] = parsed.get("private_key")
    return out


def _required_secrets_for_type(source_type: str, config: Dict[str, Any], *, creating: bool) -> Optional[str]:
    if source_type == "cloudflare":
        token = str(config.get("api_token") or "").strip()
        if creating and (not token or token == MASK):
            return "Cloudflare API token is required."
    elif source_type == "route53":
        key = str(config.get("access_key_id") or "").strip()
        secret = str(config.get("aws_secret_access_key") or "").strip()
        if creating and (not key or not secret or secret == MASK):
            return "AWS access key id and secret are required."
    elif source_type == "alidns":
        key = str(config.get("access_key_id") or "").strip()
        secret = str(config.get("access_key_secret") or "").strip()
        if creating and (not key or not secret or secret == MASK):
            return "Alibaba Cloud AccessKey id and secret are required."
    elif source_type == "azure":
        tenant = str(config.get("tenant_id") or "").strip()
        client_id = str(config.get("client_id") or "").strip()
        secret = str(config.get("client_secret") or "").strip()
        subscription = str(config.get("subscription_id") or "").strip()
        if creating and (not tenant or not client_id or not secret or secret == MASK or not subscription):
            return "Azure tenant id, client id, client secret, and subscription id are required."
    elif source_type == "gcp":
        from app.services.ingest.connectors.gcp import parse_service_account

        try:
            account = parse_service_account(config)
        except RuntimeError as exc:
            return str(exc)
        secret = str(config.get("service_account_json") or config.get("private_key") or "").strip()
        if creating and (
            not account["project_id"]
            or not account["client_email"]
            or not account["private_key"]
            or secret == MASK
        ):
            return "Paste a GCP service account JSON key (DNS Reader)."
    else:
        return "Unsupported DNS source type."
    return None


def _clean_lists(config: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(config)
    for field in ("zone_allowlist", "zone_denylist"):
        raw = out.get(field)
        if isinstance(raw, str):
            out[field] = [part.strip() for part in raw.replace(",", "\n").splitlines() if part.strip()]
        elif isinstance(raw, list):
            out[field] = [str(part).strip() for part in raw if str(part).strip()]
    if "interval_seconds" in out and out["interval_seconds"] not in (None, ""):
        try:
            out["interval_seconds"] = max(60, int(out["interval_seconds"]))
        except (TypeError, ValueError):
            out.pop("interval_seconds", None)
    return out


def create_cloud_source_service(data: Dict[str, Any], actor_username: str) -> Tuple[Dict[str, Any], int]:
    source_type = str(data.get("type") or "").strip().lower()
    display_name = str(data.get("display_name") or TYPE_LABELS.get(source_type) or source_type).strip()
    config = _normalize_provider_config(
        source_type,
        _clean_lists(data.get("config") if isinstance(data.get("config"), dict) else {}),
    )
    if source_type not in CLOUD_SOURCE_TYPES:
        return {"error": "type must be cloudflare, route53, alidns, azure, or gcp."}, 400
    if not display_name:
        return {"error": "display_name is required."}, 400
    secret_error = _required_secrets_for_type(source_type, config, creating=True)
    if secret_error:
        return {"error": secret_error}, 400
    key = f"{source_type}:{uuid.uuid4().hex[:8]}"
    source_id = create_dns_source(
        key=key,
        source_type=source_type,
        display_name=display_name,
        config=config,
    )
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="dns_source.create",
        entity_type="dns_source",
        entity_id=str(source_id),
        metadata={"type": source_type, "key": key},
    )
    source = get_dns_source(source_id, mask=True)
    return {"ok": True, "source": source}, 201


def update_cloud_source_service(
    source_id: int,
    data: Dict[str, Any],
    actor_username: str,
) -> Tuple[Dict[str, Any], int]:
    existing = get_dns_source(source_id, mask=True)
    if not existing:
        return {"error": "DNS source not found."}, 404
    if existing.get("type") not in CLOUD_SOURCE_TYPES:
        return {"error": "This source is managed elsewhere."}, 400
    config = data.get("config") if isinstance(data.get("config"), dict) else None
    if config is not None:
        config = _normalize_provider_config(str(existing.get("type")), _clean_lists(config))
        secret_error = _required_secrets_for_type(str(existing.get("type")), config, creating=False)
        if secret_error:
            return {"error": secret_error}, 400
    updated = update_dns_source(
        source_id,
        display_name=data.get("display_name"),
        enabled=data.get("enabled") if "enabled" in data else None,
        config=config,
    )
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="dns_source.update",
        entity_type="dns_source",
        entity_id=str(source_id),
        metadata={"fields": sorted(data.keys())},
    )
    return {"ok": True, "source": updated}, 200


def delete_cloud_source_service(source_id: int, actor_username: str) -> Tuple[Dict[str, Any], int]:
    existing = get_dns_source(source_id, mask=True)
    if not existing:
        return {"error": "DNS source not found."}, 404
    if existing.get("type") not in CLOUD_SOURCE_TYPES:
        return {"error": "This source is managed elsewhere."}, 400
    deleted = delete_dns_source(source_id)
    if not deleted:
        return {"error": "DNS source not found."}, 404
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="dns_source.delete",
        entity_type="dns_source",
        entity_id=str(source_id),
        metadata={"type": existing.get("type"), "display_name": existing.get("display_name")},
    )
    return {
        "ok": True,
        "message": "Connector deleted. Hosts and observations were kept.",
    }, 200


def list_source_zones_service(source_id: int) -> Tuple[Dict[str, Any], int]:
    existing = get_dns_source(source_id, mask=True)
    if not existing:
        return {"error": "DNS source not found."}, 404
    return {"zones": list_zones_for_source(source_id), "source": existing}, 200


def sync_now_service(source_id: int, actor_username: str) -> Tuple[Dict[str, Any], int]:
    existing = get_dns_source(source_id, mask=True)
    if not existing:
        return {"error": "DNS source not found."}, 404
    if existing.get("type") not in CLOUD_SOURCE_TYPES:
        return {"error": "This source is managed elsewhere."}, 400
    job_id = enqueue_source_sync(source_id)
    record_audit_event(
        actor=actor_username or "admin",
        actor_type="user",
        action="dns_source.sync_now",
        entity_type="dns_source",
        entity_id=str(source_id),
        metadata={"job_id": job_id},
    )
    return {"ok": True, "job_id": job_id}, 202


__all__ = [
    "create_cloud_source_service",
    "delete_cloud_source_service",
    "enqueue_source_sync",
    "list_cloud_sources_service",
    "list_source_zones_service",
    "source_due_for_sync",
    "sync_all_pull_sources",
    "sync_now_service",
    "sync_pull_source",
    "update_cloud_source_service",
]
