import hmac
import json
import os
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple

from app.domain.offsec.shared import safe_json_load
from app.integrations.db.connection import IntegrityError
from app.repositories import applications_repository, environments_repository, phase2b_repository

PACKAGES = {
    "owner_delivery": {"include_drafts": False, "occurrence_statuses": None, "prod_default": True},
    "wave_archive": {"include_drafts": False, "occurrence_statuses": None, "prod_default": False},
    "retest_pack": {"include_drafts": False, "occurrence_statuses": ["open", "retest"], "prod_default": False},
    "internal_draft": {"include_drafts": True, "occurrence_statuses": None, "prod_default": False},
}

CLOSED_WAVE_ERROR = "This wave has ended. Findings and wave details are read-only."


def wave_is_open(wave: Optional[Dict[str, Any]]) -> bool:
    if not wave:
        return True
    if wave.get("closed_at"):
        return False
    return str(wave.get("status") or "").strip().lower() == "open"


def reject_if_closed(wave: Optional[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], int]]:
    if wave_is_open(wave):
        return None
    return {"error": CLOSED_WAVE_ERROR}, 400


def _is_override(role: str) -> bool:
    return str(role or "").strip().lower() in {"admin", "manager"}


def package_defaults(package: str) -> Dict[str, Any]:
    key = str(package or "owner_delivery").strip() or "owner_delivery"
    if key not in PACKAGES:
        key = "owner_delivery"
    return {"package": key, **PACKAGES[key]}


def sign_export(content_hash: str) -> str:
    secret = str(os.getenv("SECRET_KEY") or "your_secret_key").encode("utf-8")
    return hmac.new(secret, str(content_hash or "").encode("utf-8"), sha256).hexdigest()


def verify_signature(content_hash: str, signature: str) -> bool:
    expected = sign_export(content_hash)
    return hmac.compare_digest(expected, str(signature or ""))


def merge_checklist_keys(raw_states: Any, extra_keys: List[str]) -> str:
    if isinstance(raw_states, dict):
        states = dict(raw_states)
    else:
        states = safe_json_load(raw_states, {})
        if not isinstance(states, dict):
            states = {}
    selected = [str(item).strip() for item in (states.get("selected") or []) if str(item).strip()]
    seen = set(selected)
    for key in extra_keys or []:
        cleaned = str(key or "").strip()
        if cleaned and cleaned not in seen:
            selected.append(cleaned)
            seen.add(cleaned)
    states["selected"] = selected
    states.setdefault("statuses", {})
    return json.dumps(states)


def verify_export(export_id: int) -> Tuple[Any, int]:
    from app.config import DB_PATH
    from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT id, content_hash, signature, file_path FROM report_exports WHERE id = ?", (export_id,))
        row = c.fetchone()
    if not row:
        return {"error": "Export not found."}, 404
    valid = verify_signature(str(row.get("content_hash") or ""), str(row.get("signature") or ""))
    return {
        "export_id": int(row["id"]),
        "valid": valid,
        "content_hash": row.get("content_hash") or "",
        "signature": row.get("signature") or "",
    }, 200


def list_waves(app_id: int) -> Tuple[Any, int]:
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    return {"waves": phase2b_repository.list_waves(app_id)}, 200


def get_wave(app_id: int, wave_id: int) -> Tuple[Any, int]:
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    from app.repositories.pentest_findings_repository import fetch_app_findings

    env_ids = phase2b_repository.wave_env_ids(wave)
    environments = []
    for env_id in env_ids:
        env = environments_repository.fetch_environment(app_id, env_id)
        if env:
            environments.append(env)
    hosts = phase2b_repository.list_live_wave_hosts(wave)
    findings, _ = fetch_app_findings(
        app_id, wave_id=int(wave["id"]), include_drafts=True, limit=200, offset=0
    )
    return {
        "wave": wave,
        "environment": environments[0] if environments else None,
        "environments": environments,
        "hosts": hosts,
        "findings": findings,
        "members": wave.get("members") or [],
        "finding_total": len(findings),
        "host_total": len(hosts),
    }, 200


def _parse_env_ids(data: Dict[str, Any]) -> List[int]:
    raw = (data or {}).get("env_ids")
    if raw in (None, "", []):
        single = (data or {}).get("environment_id")
        raw = [single] if single not in (None, "") else []
    if not isinstance(raw, list):
        raw = [raw]
    cleaned = []
    seen = set()
    for item in raw:
        try:
            env_id = int(item)
        except (TypeError, ValueError):
            continue
        if env_id in seen:
            continue
        seen.add(env_id)
        cleaned.append(env_id)
    return cleaned


def create_wave(app_id: int, data: Dict[str, Any], username: str) -> Tuple[Any, int]:
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    name = str((data or {}).get("name") or "").strip()
    if not name:
        return {"error": "name is required."}, 400
    env_ids = _parse_env_ids(data or {})
    if not env_ids:
        return {"error": "Pick at least one environment for this wave."}, 400
    known = {int(env["id"]) for env in environments_repository.fetch_environments(app_id)}
    if any(env_id not in known for env_id in env_ids):
        return {"error": "Every environment must belong to this application."}, 400
    members = data.get("members") if isinstance(data.get("members"), list) else []
    seeded = list(members)
    for env_id in env_ids:
        seeded.extend(phase2b_repository.list_acl(env_id))
    wave = phase2b_repository.create_wave(
        app_id, name, env_ids, username, str(data.get("notes") or ""), members=seeded
    )
    phase2b_repository.sync_wave_host_collaborators(int(wave["id"]), wave.get("members") or [])
    phase2b_repository.set_live_wave_host_status(wave, "Not Started")
    return {"wave": wave}, 201


def put_wave_environments(app_id: int, wave_id: int, data: Dict[str, Any]) -> Tuple[Any, int]:
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    blocked = reject_if_closed(wave)
    if blocked:
        return blocked
    env_ids = _parse_env_ids(data or {})
    if not env_ids:
        return {"error": "Pick at least one environment for this wave."}, 400
    known = {int(env["id"]) for env in environments_repository.fetch_environments(app_id)}
    if any(env_id not in known for env_id in env_ids):
        return {"error": "Every environment must belong to this application."}, 400
    updated = phase2b_repository.replace_wave_env_ids(wave_id, env_ids)
    phase2b_repository.sync_wave_host_collaborators(wave_id, updated.get("members") or wave.get("members") or [])
    host_status = "In Progress" if updated.get("started_at") else "Not Started"
    phase2b_repository.set_live_wave_host_status(updated, host_status)
    return {"wave": updated, "env_ids": phase2b_repository.wave_env_ids(updated)}, 200


def set_wave_host_scope(app_id: int, wave_id: int, data: Dict[str, Any]) -> Tuple[Any, int]:
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    blocked = reject_if_closed(wave)
    if blocked:
        return blocked
    try:
        record_ids = [int(item) for item in (data.get("record_ids") or [])]
    except (TypeError, ValueError):
        return {"error": "record_ids must be integers."}, 400
    if "in_scope" not in (data or {}):
        return {"error": "in_scope is required."}, 400
    live = {int(item["id"]) for item in phase2b_repository.list_live_wave_hosts(wave)}
    ids = [item for item in record_ids if item in live]
    if not ids:
        return {"error": "Pick hosts that belong to this wave's environments."}, 400
    updated = phase2b_repository.set_wave_host_scope(wave_id, ids, bool(data.get("in_scope")))
    return {"updated": updated, "in_scope": bool(data.get("in_scope"))}, 200


def delete_wave(app_id: int, wave_id: int) -> Tuple[Any, int]:
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    if not phase2b_repository.delete_wave(wave_id, app_id):
        return {"error": "Wave not found."}, 404
    return {"message": "Wave deleted. Findings were kept."}, 200


def put_wave_members(app_id: int, wave_id: int, data: Dict[str, Any]) -> Tuple[Any, int]:
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    blocked = reject_if_closed(wave)
    if blocked:
        return blocked
    names = data.get("usernames") if isinstance(data, dict) else None
    if not isinstance(names, list):
        return {"error": "usernames must be a list."}, 400
    opener = str(wave.get("opened_by") or "").strip()
    if opener and opener not in names:
        names = [opener, *names]
    members = phase2b_repository.replace_wave_members(wave_id, names)
    phase2b_repository.sync_wave_host_collaborators(wave_id, members)
    wave["members"] = members
    return {"wave": wave, "members": members}, 200


def claim_wave_hosts(app_id: int, wave_id: int, data: Dict[str, Any], username: str) -> Tuple[Any, int]:
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    blocked = reject_if_closed(wave)
    if blocked:
        return blocked
    actor = str(username or "").strip()
    members = [str(name).strip() for name in (wave.get("members") or []) if str(name).strip()]
    opener = str(wave.get("opened_by") or "").strip()
    if actor not in members and actor != opener:
        return {"error": "Only testers on this wave can take a host."}, 403
    try:
        requested = [int(item) for item in (data.get("record_ids") or [])]
    except (TypeError, ValueError):
        return {"error": "record_ids must be integers."}, 400
    snapshot = set(phase2b_repository._snapshot_ids(wave))
    ids = [item for item in requested if item in snapshot]
    if not ids:
        return {"error": "Pick a host from this wave."}, 400
    updated = phase2b_repository.assign_record_testers(ids, actor)
    phase2b_repository.sync_wave_host_collaborators(wave_id, members or [actor, opener])
    return {"updated": updated, "tested_by": actor}, 200


def start_wave(app_id: int, wave_id: int) -> Tuple[Any, int]:
    wave = phase2b_repository.get_wave(wave_id)
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return {"error": "Wave not found."}, 404
    if str(wave.get("status") or "") != "open":
        return {"error": "Only an open wave can be started."}, 400
    if wave.get("started_at"):
        return {"error": "Wave is already started."}, 400
    started = phase2b_repository.start_wave(wave_id, app_id)
    if not started:
        return {"error": "Wave not found or already started."}, 400
    return {"wave": started}, 200


def close_wave(app_id: int, wave_id: int) -> Tuple[Any, int]:
    wave = phase2b_repository.close_wave(wave_id, app_id)
    if not wave:
        return {"error": "Wave not found or already closed."}, 404
    return {"wave": wave}, 200


def get_acl(app_id: int, env_id: int) -> Tuple[Any, int]:
    env = environments_repository.fetch_environment(app_id, env_id)
    if not env:
        return {"error": "Environment not found."}, 404
    return {"usernames": phase2b_repository.list_acl(env_id)}, 200


def put_acl(app_id: int, env_id: int, data: Dict[str, Any]) -> Tuple[Any, int]:
    env = environments_repository.fetch_environment(app_id, env_id)
    if not env:
        return {"error": "Environment not found."}, 404
    names = data.get("usernames") if isinstance(data, dict) else None
    if not isinstance(names, list):
        return {"error": "usernames must be a list."}, 400
    return {"usernames": phase2b_repository.replace_acl(env_id, names)}, 200


def get_env_checklists(app_id: int, env_id: int) -> Tuple[Any, int]:
    env = environments_repository.fetch_environment(app_id, env_id)
    if not env:
        return {"error": "Environment not found."}, 404
    return {"template_keys": phase2b_repository.list_env_checklists(env_id)}, 200


def put_env_checklists(app_id: int, env_id: int, data: Dict[str, Any]) -> Tuple[Any, int]:
    env = environments_repository.fetch_environment(app_id, env_id)
    if not env:
        return {"error": "Environment not found."}, 404
    keys = data.get("template_keys") if isinstance(data, dict) else None
    if not isinstance(keys, list):
        return {"error": "template_keys must be a list."}, 400
    return {"template_keys": phase2b_repository.replace_env_checklists(env_id, keys)}, 200


def list_zones(app_id: Optional[int] = None) -> Tuple[Any, int]:
    return {"zones": phase2b_repository.list_zones(app_id)}, 200


def create_zone(data: Dict[str, Any]) -> Tuple[Any, int]:
    suffix = str((data or {}).get("suffix") or "").strip()
    if not suffix:
        return {"error": "suffix is required."}, 400
    application_id = data.get("application_id")
    try:
        app_id = int(application_id) if application_id not in (None, "", "null") else None
    except (TypeError, ValueError):
        return {"error": "Invalid application_id."}, 400
    try:
        zone = phase2b_repository.create_zone(
            suffix,
            str(data.get("display_name") or ""),
            app_id,
            str(data.get("notes") or ""),
        )
    except IntegrityError:
        return {"error": "Zone suffix already exists."}, 409
    return {"zone": zone}, 201


def delete_zone(zone_id: int) -> Tuple[Any, int]:
    if not phase2b_repository.delete_zone(zone_id):
        return {"error": "Zone not found."}, 404
    return {"message": "Zone deleted."}, 200


def share_host(app_id: int, record_id: int, data: Dict[str, Any]) -> Tuple[Any, int]:
    try:
        consumer = int((data or {}).get("consumer_application_id"))
    except (TypeError, ValueError):
        return {"error": "consumer_application_id is required."}, 400
    if consumer == app_id:
        return {"error": "Cannot share a host with its owning app."}, 400
    if not applications_repository.fetch_application(consumer):
        return {"error": "Consumer application not found."}, 404
    if not phase2b_repository.share_host(record_id, app_id, consumer):
        return {"error": "Host not found on this application."}, 404
    return {"message": "Host shared."}, 200


def list_shared(app_id: int) -> Tuple[Any, int]:
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    return {"hosts": phase2b_repository.list_shared_hosts(app_id)}, 200


def visible_env_ids(app_id: int, username: str, role: str) -> Optional[List[int]]:
    app = applications_repository.fetch_application(app_id) or {}
    return phase2b_repository.allowed_environment_ids(
        app_id,
        username,
        is_override=_is_override(role),
        app_lead=str(app.get("app_lead") or ""),
    )
