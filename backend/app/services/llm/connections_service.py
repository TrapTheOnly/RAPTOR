"""Admin CRUD for LLM provider connections."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.llm_connections_repository import (
    create_connection,
    delete_connection,
    ensure_local_connection,
    get_connection,
    get_local_connection,
    list_connections,
    update_connection,
)
from app.repositories.scanner_config_repository import get_scanner_config, update_scanner_config
from app.services.audit_service import record_audit_event
from app.services.llm.catalog import (
    CatalogError,
    apply_model_updates,
    list_models,
    merge_models,
    probe_connection,
)
from app.services.llm.recipes import (
    LOCAL_MODEL_ID,
    LOCAL_TYPE,
    USER_CREATABLE_TYPES,
    recipe_for,
    resolve_base_url,
    type_label,
)
from app.services.llm.secrets import MASK

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _public_connection(row: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(row)
    payload["type_label"] = type_label(str(row.get("type") or ""))
    payload["protocol"] = str((recipe_for(str(row.get("type") or "")) or {}).get("protocol") or "")
    payload["can_delete"] = str(row.get("type") or "") != LOCAL_TYPE
    return payload


def list_connections_service() -> Tuple[Dict[str, Any], int]:
    ensure_local_connection()
    rows = [_public_connection(item) for item in list_connections(mask=True)]
    return {"connections": rows}, 200


def get_connection_service(connection_id: int) -> Tuple[Dict[str, Any], int]:
    row = get_connection(connection_id, mask=True)
    if not row:
        return {"error": "Connection not found."}, 404
    return {"connection": _public_connection(row)}, 200


def _required_secrets(provider_type: str, config: Dict[str, Any], *, creating: bool) -> Optional[str]:
    recipe = recipe_for(provider_type)
    if not recipe:
        return "Unknown provider type."
    if not creating:
        return None
    for field in recipe.get("required_on_create") or ():
        value = str(config.get(field) or "").strip()
        if not value or value == MASK:
            return f"{field} is required."
    if provider_type == "bedrock":
        bearer = str(config.get("aws_bearer_token") or "").strip()
        access = str(config.get("access_key_id") or "").strip()
        secret = str(config.get("aws_secret_access_key") or "").strip()
        if not bearer and not (access and secret):
            return "Bedrock needs a bearer token or access key + secret."
    return None


def create_connection_service(data: Dict[str, Any], actor: str) -> Tuple[Dict[str, Any], int]:
    provider_type = str(data.get("type") or "").strip().lower()
    if provider_type not in USER_CREATABLE_TYPES:
        return {"error": "Unsupported provider type."}, 400
    if provider_type == LOCAL_TYPE:
        return {"error": "The local runtime is built in."}, 400
    display_name = str(data.get("display_name") or type_label(provider_type)).strip()
    if not display_name:
        return {"error": "display_name is required."}, 400
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    secret_error = _required_secrets(provider_type, config, creating=True)
    if secret_error:
        return {"error": secret_error}, 400
    models = apply_model_updates([], data.get("models") if isinstance(data.get("models"), list) else [])
    connection_id = create_connection(
        provider_type=provider_type,
        display_name=display_name,
        config=config,
        models=models,
        enabled=True if data.get("enabled") is None else bool(data.get("enabled")),
    )
    if not models:
        try:
            refresh_models_service(connection_id, actor)
        except Exception:
            logger.debug("Initial model refresh skipped", exc_info=True)
    record_audit_event(
        actor=actor or "admin",
        actor_type="user",
        action="llm_connection.create",
        entity_type="llm_connection",
        entity_id=str(connection_id),
        metadata={"type": provider_type},
    )
    row = get_connection(connection_id, mask=True)
    return {"ok": True, "connection": _public_connection(row or {})}, 201


def update_connection_service(
    connection_id: int,
    data: Dict[str, Any],
    actor: str,
) -> Tuple[Dict[str, Any], int]:
    existing = get_connection(connection_id, mask=True)
    if not existing:
        return {"error": "Connection not found."}, 404
    if str(existing.get("type") or "") == LOCAL_TYPE:
        allowed = set(data.keys()) - {"enabled", "display_name", "models"}
        if allowed:
            return {"error": "Local runtime settings are managed on the Local model tab."}, 400
    config = data.get("config") if isinstance(data.get("config"), dict) else None
    models = apply_model_updates(
        existing.get("models") or [],
        data.get("models") if isinstance(data.get("models"), list) else None,
    )
    if "models" not in data:
        models = None
    updated = update_connection(
        connection_id,
        display_name=data.get("display_name"),
        enabled=data.get("enabled") if "enabled" in data else None,
        config=config,
        models=models,
        updated_by=actor,
    )
    record_audit_event(
        actor=actor or "admin",
        actor_type="user",
        action="llm_connection.update",
        entity_type="llm_connection",
        entity_id=str(connection_id),
        metadata={"fields": sorted(data.keys())},
    )
    return {"ok": True, "connection": _public_connection(updated or {})}, 200


def delete_connection_service(connection_id: int, actor: str) -> Tuple[Dict[str, Any], int]:
    existing = get_connection(connection_id, mask=True)
    if not existing:
        return {"error": "Connection not found."}, 404
    if str(existing.get("type") or "") == LOCAL_TYPE:
        return {"error": "The local runtime cannot be deleted."}, 400
    cfg = get_scanner_config() or {}
    if int(cfg.get("active_connection_id") or 0) == connection_id:
        update_scanner_config({"active_connection_id": None, "active_model_id": ""})
    delete_connection(connection_id)
    record_audit_event(
        actor=actor or "admin",
        actor_type="user",
        action="llm_connection.delete",
        entity_type="llm_connection",
        entity_id=str(connection_id),
        metadata={"type": existing.get("type")},
    )
    return {"ok": True}, 200


def refresh_models_service(connection_id: int, actor: str = "") -> Tuple[Dict[str, Any], int]:
    existing = get_connection(connection_id, decrypt=True, mask=False)
    if not existing:
        return {"error": "Connection not found."}, 404
    try:
        fetched = list_models(str(existing.get("type")), existing.get("config") or {})
    except CatalogError as exc:
        update_connection(connection_id, last_error=str(exc), last_checked_at=_utc_now(), updated_by=actor or None)
        return {"error": str(exc), "connection": _public_connection(get_connection(connection_id, mask=True) or {})}, 502
    merged = merge_models(existing.get("models") or [], fetched)
    updated = update_connection(
        connection_id,
        models=merged,
        last_error="",
        last_checked_at=_utc_now(),
        updated_by=actor or None,
    )
    return {"ok": True, "connection": _public_connection(updated or {})}, 200


def test_connection_service(connection_id: int, actor: str = "") -> Tuple[Dict[str, Any], int]:
    existing = get_connection(connection_id, decrypt=True, mask=False)
    if not existing:
        return {"error": "Connection not found."}, 404
    ok, message = probe_connection(
        str(existing.get("type")),
        existing.get("config") or {},
        existing.get("models") or [],
    )
    update_connection(
        connection_id,
        last_error="" if ok else message,
        last_checked_at=_utc_now(),
        updated_by=actor or None,
    )
    row = get_connection(connection_id, mask=True)
    status = 200 if ok else 502
    return {"ok": ok, "message": message, "connection": _public_connection(row or {})}, status


def find_selected_model(connection: Dict[str, Any], model_id: str) -> Optional[Dict[str, Any]]:
    wanted = str(model_id or "").strip()
    for item in connection.get("models") or []:
        if str(item.get("id") or "") == wanted:
            return dict(item)
    return None


def model_is_usable(model: Optional[Dict[str, Any]]) -> bool:
    if not model:
        return False
    if model.get("selected") is False:
        return False
    if model.get("tools") is False:
        return False
    return True


def maybe_autoselect_local() -> None:
    cfg = get_scanner_config() or {}
    if str(cfg.get("active_model_id") or "").strip() and cfg.get("active_connection_id"):
        return
    local = get_local_connection(mask=True)
    if not local:
        return
    from app.services.llm.local_llm_service import fetch_local_status

    status = fetch_local_status()
    if str(status.get("state") or "") != "ready":
        return
    update_scanner_config(
        {
            "active_connection_id": int(local["id"]),
            "active_model_id": LOCAL_MODEL_ID,
        }
    )


def build_scan_job(
    record_id: int,
    cfg: Dict[str, Any],
    *,
    allow_destructive: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[Dict[str, Any], int]]]:
    connection_id = cfg.get("active_connection_id")
    model_id = str(cfg.get("active_model_id") or "").strip()
    if not connection_id or not model_id:
        return None, ({"error": "No active scan model is configured."}, 503)
    connection = get_connection(int(connection_id), decrypt=True, mask=False)
    if not connection:
        return None, ({"error": "Active LLM connection is missing."}, 503)
    if not connection.get("enabled"):
        return None, ({"error": "Active LLM connection is disabled."}, 503)
    model = find_selected_model(connection, model_id)
    if not model_is_usable(model) and str(connection.get("type")) == LOCAL_TYPE:
        model = find_selected_model(connection, LOCAL_MODEL_ID) or {
            "id": LOCAL_MODEL_ID,
            "selected": True,
            "tools": True,
        }
    if not model_is_usable(model):
        return None, ({"error": "Active model is not enabled or does not support tools."}, 503)
    kind = str(connection.get("type") or "")
    if kind == LOCAL_TYPE:
        from app.services.llm.local_llm_service import fetch_local_status

        status = fetch_local_status()
        if str(status.get("state") or "") != "ready":
            return None, ({"error": "RAPTOR Local is not ready. Install it in Admin Settings."}, 503)
    recipe = recipe_for(kind) or {}
    config = connection.get("config") or {}
    from app.services.llm.rates import documented_rates

    input_cost = model.get("input_cost_per_1m")
    output_cost = model.get("output_cost_per_1m")
    documented = documented_rates(model_id)
    if input_cost in (None, ""):
        input_cost = documented[0] if documented else 0
    if output_cost in (None, ""):
        output_cost = documented[1] if documented else 0
    if kind == LOCAL_TYPE:
        input_cost = 0
        output_cost = 0
    extra_headers = config.get("extra_headers") if isinstance(config.get("extra_headers"), dict) else {}
    job = {
        "record_id": record_id,
        "provider_type": kind,
        "provider_display_name": connection.get("display_name") or type_label(kind),
        "protocol": recipe.get("protocol"),
        "base_url": resolve_base_url(kind, config),
        "api_key": str(config.get("api_key") or config.get("aws_bearer_token") or ""),
        "model_id": model_id,
        "aws_region": str(config.get("aws_region") or cfg.get("aws_region") or "us-east-1"),
        "aws_access_key": str(config.get("access_key_id") or ""),
        "aws_secret_key": str(config.get("aws_secret_access_key") or ""),
        "aws_session_token": str(config.get("aws_session_token") or ""),
        "aws_bearer_token": str(config.get("aws_bearer_token") or ""),
        "azure_api_version": str(config.get("api_version") or "2024-10-21"),
        "extra_headers": extra_headers,
        "project_ocid": str(config.get("project_ocid") or ""),
        "cost_limit_usd": float(cfg.get("cost_limit_usd") or 5.0),
        "input_cost_per_1m": float(input_cost or 0),
        "output_cost_per_1m": float(output_cost or 0),
        "thinking_budget_tokens": int(cfg.get("thinking_budget_tokens") or 8000),
        "max_turns": int(cfg.get("max_turns") or 40),
        "proxy_url": str(cfg.get("proxy_url") or ""),
        "proxy_username": str(cfg.get("proxy_username") or ""),
        "proxy_password": str(cfg.get("proxy_password") or ""),
        "allow_destructive_tools": bool(allow_destructive),
    }
    return job, None


__all__ = [
    "build_scan_job",
    "create_connection_service",
    "delete_connection_service",
    "get_connection_service",
    "list_connections_service",
    "maybe_autoselect_local",
    "refresh_models_service",
    "test_connection_service",
    "update_connection_service",
]
