import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx

from app.repositories.scanner_config_repository import (
    count_running_scans,
    get_scanner_config,
    update_scanner_config,
)

logger = logging.getLogger(__name__)

SCANNER_BASE_URL = os.getenv("SCANNER_BASE_URL", "http://scanner:8082")
SCANNER_INTERNAL_TOKEN = os.getenv("SCANNER_INTERNAL_TOKEN", "")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    safe = dict(cfg)
    if safe.get("proxy_password"):
        safe["proxy_password"] = "••••••••"
    return safe


def get_scanner_config_payload() -> Tuple[Dict[str, Any], int]:
    try:
        from app.repositories.llm_connections_repository import ensure_local_connection
        from app.services.llm.connections_service import maybe_autoselect_local

        ensure_local_connection()
        maybe_autoselect_local()
        cfg = get_scanner_config()
        if not cfg:
            return {"error": "Scanner config not found."}, 404
        return {"config": _safe_config(cfg)}, 200
    except Exception as exc:
        logger.error(f"Failed to fetch scanner config: {exc}")
        return {"error": "Failed to fetch scanner config."}, 500


def _validate_active_model(cfg: Dict[str, Any]) -> Optional[str]:
    from app.services.llm.connections_service import (
        find_selected_model,
        model_is_usable,
    )
    from app.repositories.llm_connections_repository import get_connection
    from app.services.llm.recipes import LOCAL_TYPE
    from app.services.llm.local_llm_service import fetch_local_status

    connection_id = cfg.get("active_connection_id")
    model_id = str(cfg.get("active_model_id") or "").strip()
    if not connection_id or not model_id:
        return "Pick an active scan model before enabling the scanner."
    connection = get_connection(int(connection_id), mask=True)
    if not connection or not connection.get("enabled"):
        return "Active LLM connection is missing or disabled."
    model = find_selected_model(connection, model_id)
    if not model_is_usable(model) and str(connection.get("type")) != LOCAL_TYPE:
        return "Active model is not enabled or does not support tools."
    if str(connection.get("type")) == LOCAL_TYPE:
        status = fetch_local_status()
        if str(status.get("state") or "") != "ready":
            return "Install RAPTOR Local (or pick an API model) before enabling the scanner."
    return None


def update_scanner_config_payload(
    fields: Dict[str, Any], actor: str
) -> Tuple[Dict[str, Any], int]:
    allowed = {
        "aws_region", "bedrock_model_id", "cost_limit_usd",
        "input_cost_per_1m", "output_cost_per_1m",
        "max_concurrent_scans", "enabled",
        "proxy_url", "proxy_username", "proxy_password",
        "allow_destructive_tools",
        "active_connection_id", "active_model_id",
        "thinking_budget_tokens", "max_turns",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return {"error": "No valid fields to update."}, 400

    if updates.get("proxy_password") == "••••••••":
        existing = get_scanner_config()
        updates["proxy_password"] = (existing or {}).get("proxy_password", "") if existing else ""

    if "enabled" in updates:
        updates["enabled"] = 1 if updates["enabled"] else 0
    if "allow_destructive_tools" in updates:
        updates["allow_destructive_tools"] = 1 if updates["allow_destructive_tools"] else 0
    if "max_concurrent_scans" in updates:
        try:
            val = int(updates["max_concurrent_scans"])
            if val < 1 or val > 10:
                return {"error": "max_concurrent_scans must be between 1 and 10."}, 400
            updates["max_concurrent_scans"] = val
        except (TypeError, ValueError):
            return {"error": "max_concurrent_scans must be an integer."}, 400
    if "thinking_budget_tokens" in updates:
        try:
            val = int(updates["thinking_budget_tokens"])
            if val < 0 or val > 64000:
                return {"error": "thinking_budget_tokens must be between 0 and 64000."}, 400
            updates["thinking_budget_tokens"] = val
        except (TypeError, ValueError):
            return {"error": "thinking_budget_tokens must be an integer."}, 400
    if "max_turns" in updates:
        try:
            val = int(updates["max_turns"])
            if val < 1 or val > 200:
                return {"error": "max_turns must be between 1 and 200."}, 400
            updates["max_turns"] = val
        except (TypeError, ValueError):
            return {"error": "max_turns must be an integer."}, 400
    if "active_connection_id" in updates:
        raw = updates["active_connection_id"]
        if raw in (None, "", 0, "0"):
            updates["active_connection_id"] = None
        else:
            try:
                updates["active_connection_id"] = int(raw)
            except (TypeError, ValueError):
                return {"error": "active_connection_id must be an integer."}, 400
    if "active_model_id" in updates:
        updates["active_model_id"] = str(updates["active_model_id"] or "").strip()
    for cost_field in ("cost_limit_usd", "input_cost_per_1m", "output_cost_per_1m"):
        if cost_field not in updates:
            continue
        try:
            val = float(updates[cost_field])
            if val < 0:
                return {"error": f"{cost_field} must be at least 0."}, 400
            updates[cost_field] = val
        except (TypeError, ValueError):
            return {"error": f"{cost_field} must be a number."}, 400

    merged = dict(get_scanner_config() or {})
    merged.update(updates)
    enabling = updates.get("enabled") == 1
    switching_model = "active_connection_id" in updates or "active_model_id" in updates
    if int(merged.get("enabled") or 0) and (enabling or switching_model):
        error = _validate_active_model(merged)
        if error:
            return {"error": error}, 400

    updates["updated_by"] = actor
    updates["updated_at"] = _utc_now_iso()

    try:
        update_scanner_config(updates)
        cfg = get_scanner_config()
        return {"message": "Scanner config updated.", "config": _safe_config(cfg or {})}, 200
    except Exception as exc:
        logger.error(f"Failed to update scanner config: {exc}")
        return {"error": "Failed to update scanner config."}, 500


def launch_scan_payload(record_id: int) -> Tuple[Dict[str, Any], int]:
    return {
        "error": "AI scans cover every in-scope host on the started wave. Launch from the wave, not a single host."
    }, 400


def launch_wave_scan_payload(
    app_id: int,
    wave_id: int,
    actor: str = "",
    options: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], int]:
    try:
        cfg = get_scanner_config()
    except Exception as exc:
        logger.error(f"Failed to read scanner config: {exc}")
        return {"error": "Failed to read scanner config."}, 500

    if not cfg:
        return {"error": "Scanner is not configured."}, 503
    if not int(cfg.get("enabled") or 0):
        return {"error": "Scanner is disabled. Enable it in Admin Settings."}, 503
    ready_error = _validate_active_model(cfg)
    if ready_error:
        return {"error": ready_error}, 503

    from app.repositories.phase2b_repository import (
        count_running_scans_for_env,
        fetch_host_env,
        get_wave,
        list_live_wave_hosts,
    )
    from app.repositories.scan_jobs_repository import (
        count_running_scan_jobs,
        create_scan_job,
        running_job_for_wave,
        scan_jobs_table_ready,
        update_scan_job,
    )
    from app.repositories.service_api_repository import update_pentest_fields

    wave = get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    if str(wave.get("status") or "") != "open":
        return {"error": "Launch scans from an open, started wave."}, 400
    if not wave.get("started_at"):
        return {"error": "Start the wave before launching scans."}, 400

    hosts = [host for host in list_live_wave_hosts(wave) if host.get("in_scope") is not False]
    if not hosts:
        return {"error": "Mark at least one host in scope before launching a scan."}, 400

    option_extra, option_error = _launch_options(options)
    if option_error:
        return {"error": option_error}, 400

    if scan_jobs_table_ready() and running_job_for_wave(wave_id):
        return {"error": "A scan is already running for this wave."}, 409
    if any(str(host.get("scan_status") or "idle") == "running" for host in hosts):
        return {"error": "A scan is already running for this wave."}, 409

    try:
        running = count_running_scan_jobs() if scan_jobs_table_ready() else count_running_scans()
        max_concurrent = int(cfg.get("max_concurrent_scans") or 2)
        if running >= max_concurrent:
            return {
                "error": f"Maximum concurrent scans reached ({max_concurrent}). Try again later."
            }, 429
    except Exception as exc:
        logger.error(f"Failed to count running scans: {exc}")
        return {"error": "Failed to check scan capacity."}, 500

    allow_destructive = bool(int(cfg.get("allow_destructive_tools") or 0))
    for host in hosts:
        env = fetch_host_env(int(host["id"])) or {}
        env_id = env.get("id")
        if not env_id:
            continue
        try:
            env_max = int(env.get("max_concurrent_scans") or 1)
            env_running = count_running_scans_for_env(int(env_id))
            if env_running >= max(env_max, 1):
                return {
                    "error": (
                        f"Environment scan ceiling reached ({env_max}). "
                        "Wait for a running scan in this environment to finish."
                    )
                }, 429
        except Exception as exc:
            logger.error(f"Failed to count environment scans for wave {wave_id}: {exc}")
            return {"error": "Failed to check environment scan capacity."}, 500
        allow_destructive = allow_destructive and bool(int(env.get("allow_destructive") or 0))

    record_ids = [int(host["id"]) for host in hosts]
    host_payload = [
        {
            "record_id": int(host["id"]),
            "name": host.get("name") or "",
            "ip_address": host.get("ip_address") or "",
        }
        for host in hosts
    ]
    scan_title = ""
    job_row = None
    if scan_jobs_table_ready():
        job_row = create_scan_job(
            application_id=app_id,
            wave_id=wave_id,
            record_ids=record_ids,
            launched_by=actor or "",
            provider_type=str(cfg.get("active_connection_id") or ""),
            model_id=str(cfg.get("active_model_id") or ""),
            title="",
            status="naming",
        )
    try:
        from app.services.engagement_namer import app_and_wave_names, name_engagement

        names = app_and_wave_names(wave)
        scan_title = name_engagement(
            kind="ai_scan",
            wave_name=names["wave_name"],
            app_name=names["app_name"],
            host_count=len(record_ids),
            extra=str(option_extra.get("operator_brief") or ""),
        )
    except Exception as exc:
        logger.info("AI scan naming fell back: %s", exc)
        from app.services.engagement_namer import fallback_title

        scan_title = fallback_title(
            kind="ai_scan",
            host_count=len(record_ids),
            wave_name=str(wave.get("name") or ""),
        )
    if job_row:
        update_scan_job(int(job_row["id"]), {"title": scan_title, "status": "running"})

    for record_id in record_ids:
        try:
            update_pentest_fields(record_id, {"scan_status": "running"})
        except Exception as exc:
            logger.warning("Failed to mark record %s running: %s", record_id, exc)

    extra = {
        "record_ids": record_ids,
        "hosts": host_payload,
        "wave_id": int(wave_id),
        "application_id": int(app_id),
        "job_id": int(job_row["id"]) if job_row else 0,
        **option_extra,
    }
    try:
        _dispatch_scan(record_ids[0], cfg, allow_destructive=allow_destructive, extra=extra)
    except Exception as exc:
        logger.error(f"Failed to dispatch wave scan {wave_id}: {exc}")
        if job_row:
            update_scan_job(int(job_row["id"]), {"status": "failed", "last_error": str(exc)[:300]})
        for record_id in record_ids:
            try:
                update_pentest_fields(record_id, {"scan_status": "idle"})
            except Exception:
                pass
        return {"error": _dispatch_error_message(exc)}, 502

    from app.services.audit_service import record_audit_event

    try:
        record_audit_event(
            actor=actor or "scanner",
            actor_type="user",
            action="scan.launch",
            entity_type="wave",
            entity_id=str(wave_id),
            metadata={
                "host_count": len(record_ids),
                "record_ids": record_ids,
                "job_id": extra["job_id"],
                "model_id": str(cfg.get("active_model_id") or ""),
            },
        )
    except Exception as exc:
        logger.warning("Failed to audit wave scan launch for %s: %s", wave_id, exc)
    return {
        "message": "Scan launched.",
        "wave_id": wave_id,
        "job_id": extra["job_id"],
        "record_ids": record_ids,
        "host_count": len(record_ids),
    }, 202


def reset_wave_scan_payload(app_id: int, wave_id: int) -> Tuple[Dict[str, Any], int]:
    from app.repositories.phase2b_repository import get_wave, list_live_wave_hosts
    from app.repositories.scan_events_repository import delete_scan_events_for_records
    from app.repositories.scan_jobs_repository import running_job_for_wave, update_scan_job
    from app.repositories.service_api_repository import update_pentest_fields

    wave = get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    hosts = [host for host in list_live_wave_hosts(wave) if host.get("in_scope") is not False]
    record_ids = [int(host["id"]) for host in hosts]
    job = running_job_for_wave(wave_id)
    if job:
        update_scan_job(int(job["id"]), {"status": "failed", "last_error": "reset"})
    for record_id in record_ids:
        try:
            update_pentest_fields(record_id, {"scan_status": "idle"})
        except Exception as exc:
            logger.warning("Failed to reset scan status for %s: %s", record_id, exc)
    if record_ids:
        delete_scan_events_for_records(record_ids)
    return {"message": "Scan reset. Previous results cleared.", "record_ids": record_ids}, 200


def stop_wave_scan_payload(app_id: int, wave_id: int) -> Tuple[Dict[str, Any], int]:
    from app.repositories.phase2b_repository import get_wave, list_live_wave_hosts
    from app.repositories.scan_events_repository import insert_scan_event
    from app.repositories.scan_jobs_repository import running_job_for_wave, update_scan_job
    from app.repositories.service_api_repository import update_pentest_fields

    wave = get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    hosts = [host for host in list_live_wave_hosts(wave) if host.get("in_scope") is not False]
    record_ids = [int(host["id"]) for host in hosts]
    job = running_job_for_wave(wave_id)
    if not job:
        return {"error": "No scan is running for this wave."}, 409
    job_id = int(job["id"])
    notified = False
    try:
        _stop_scan(job_id)
        notified = True
    except Exception as exc:
        logger.warning("Scanner stop for job %s failed: %s", job_id, exc)
    update_scan_job(job_id, {"status": "failed", "last_error": "stopped"})
    for record_id in record_ids:
        try:
            update_pentest_fields(record_id, {"scan_status": "failed"})
        except Exception as exc:
            logger.warning("Failed to mark record %s stopped: %s", record_id, exc)
    if not notified and record_ids:
        insert_scan_event(
            record_ids[0],
            "status",
            {
                "scan_status": "failed",
                "reason": "stopped",
                "wave_complete": True,
                "record_ids": record_ids,
            },
            job_id=job_id,
        )
    return {"message": "Scan stop requested.", "job_id": job_id, "record_ids": record_ids}, 200


OPERATOR_BRIEF_MAX = 4000


def _launch_options(raw: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Optional[str]]:
    raw = raw or {}
    extra: Dict[str, Any] = {}
    brief = str(raw.get("operator_brief") or raw.get("details") or "").strip()
    if brief:
        extra["operator_brief"] = brief[:OPERATOR_BRIEF_MAX]
    if raw.get("max_turns") not in (None, ""):
        try:
            turns = int(raw.get("max_turns"))
        except (TypeError, ValueError):
            return {}, "max_turns must be an integer"
        if turns < 1 or turns > 200:
            return {}, "max_turns must be between 1 and 200"
        extra["max_turns"] = turns
    if raw.get("skip_port_discovery"):
        extra["skip_port_discovery"] = True
    return extra, None


def _dispatch_error_message(exc: Exception) -> str:
    text = str(exc or "")
    lowered = text.lower()
    if "connect" in lowered or "name or service not known" in lowered or "nodename" in lowered:
        return (
            "Scanner sidecar is not running. Start the stack with "
            "`./scripts/docker_runner.sh --with-scanner --build` "
            "(Kali + scanner + local-llm)."
        )
    if "401" in text or "unauthorized" in lowered:
        return "Scanner rejected the job (internal token mismatch)."
    if text.startswith("Scanner returned"):
        return text
    return "Failed to dispatch scan to scanner service."


def _dispatch_scan(
    record_id: int,
    cfg: Dict[str, Any],
    allow_destructive: Optional[bool] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    from app.services.llm.connections_service import build_scan_job

    if allow_destructive is None:
        allow_destructive = bool(int(cfg.get("allow_destructive_tools") or 0))
    body, error = build_scan_job(record_id, cfg, allow_destructive=allow_destructive)
    if error:
        payload, status = error
        raise RuntimeError(payload.get("error") or f"Dispatch failed ({status})")
    if extra:
        body.update(extra)
    url = f"{SCANNER_BASE_URL}/scans"
    headers = {"X-Scanner-Token": SCANNER_INTERNAL_TOKEN}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=body, headers=headers)
    except httpx.ConnectError as exc:
        raise RuntimeError(f"connect failed: {exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"connect failed: {exc}") from exc
    if resp.status_code >= 400:
        raise RuntimeError(f"Scanner returned {resp.status_code}: {resp.text[:200]}")


def _stop_scan(job_id: int) -> None:
    url = f"{SCANNER_BASE_URL}/scans/{int(job_id)}/stop"
    headers = {"X-Scanner-Token": SCANNER_INTERNAL_TOKEN}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers)
    except httpx.ConnectError as exc:
        raise RuntimeError(f"connect failed: {exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"connect failed: {exc}") from exc
    if resp.status_code == 404:
        return
    if resp.status_code >= 400:
        raise RuntimeError(f"Scanner returned {resp.status_code}: {resp.text[:200]}")


__all__ = [
    "get_scanner_config_payload",
    "launch_scan_payload",
    "launch_wave_scan_payload",
    "reset_wave_scan_payload",
    "stop_wave_scan_payload",
    "update_scanner_config_payload",
]
