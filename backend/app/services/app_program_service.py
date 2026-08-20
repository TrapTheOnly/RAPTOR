import logging
from typing import Any, Dict, List, Optional, Tuple

from app.integrations.db.connection import IntegrityError
from app.repositories import (
    applications_repository,
    environments_repository,
    pentest_findings_repository,
    phase2b_repository,
)
from app.repositories.environments_repository import suggest_env_slug
from app.repositories.records_query_repository import fetch_record_by_id
from app.repositories.offsec.offsec_records import enforce_pentest_record_access
from app.services import phase2b_service, records_service
from app.services.authorization_service import user_has_permission

logger = logging.getLogger(__name__)


def _acl_env_ids(app_id: int, username: str = "", role: str = "") -> Optional[List[int]]:
    if not username:
        return None
    return phase2b_service.visible_env_ids(app_id, username, role)


def _deny_env(allowed: Optional[List[int]], env_id: Optional[int]) -> bool:
    if allowed is None or env_id is None:
        return False
    return int(env_id) not in {int(item) for item in allowed}


def _host_access_error(
    record_id: Any,
    username: str,
    role: str,
    action_verb: str = "modify",
) -> Optional[Tuple[Dict[str, Any], int]]:
    if not username:
        return None
    allowed, error = enforce_pentest_record_access(
        record_id,
        action_verb,
        username=username,
        role=role,
    )
    if not allowed:
        return {"error": error}, 403
    record = fetch_record_by_id(record_id)
    if not record:
        return None
    app_id = record.get("application_id")
    env_id = record.get("environment_id")
    if app_id and env_id and _deny_env(_acl_env_ids(int(app_id), username, role), int(env_id)):
        return {"error": "Environment is not visible to this user."}, 403
    return None


def _finding_host_access_error(
    finding: Optional[Dict[str, Any]],
    username: str,
    role: str,
    action_verb: str = "access",
) -> Optional[Tuple[Dict[str, Any], int]]:
    if not finding:
        return None
    record_id = finding.get("record_id")
    if record_id in (None, "", 0):
        return None
    return _host_access_error(record_id, username, role, action_verb)


def _reject_closed_finding_wave(finding: Optional[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], int]]:
    if not finding:
        return None
    wave_id = finding.get("discovered_wave_id")
    if wave_id in (None, "", 0):
        return None
    wave = phase2b_repository.get_wave(int(wave_id))
    return phase2b_service.reject_if_closed(wave)


def _require_open_wave(app_id: int, wave_id: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[Dict[str, Any], int]]]:
    if wave_id in (None, "", 0):
        return None, None
    wave = phase2b_repository.get_wave(int(wave_id))
    if not wave or int(wave.get("application_id") or 0) != int(app_id):
        return None, ({"error": "Wave not found."}, 404)
    blocked = phase2b_service.reject_if_closed(wave)
    if blocked:
        return None, blocked
    return wave, None


def _page(limit: Any, offset: Any) -> Tuple[int, int]:
    try:
        parsed_limit = int(limit)
    except (TypeError, ValueError):
        parsed_limit = 50
    try:
        parsed_offset = int(offset)
    except (TypeError, ValueError):
        parsed_offset = 0
    return min(max(parsed_limit, 1), 200), max(parsed_offset, 0)


def list_apps() -> Tuple[Any, int]:
    return records_service.get_applications()


def get_app(app_id: int, username: str = "", role: str = "") -> Tuple[Dict[str, Any], int]:
    app = applications_repository.fetch_application(app_id)
    if not app:
        return {"error": "Application not found."}, 404
    environments = environments_repository.fetch_environments(app_id)
    allowed = _acl_env_ids(app_id, username, role)
    if allowed is not None:
        allowed_set = {int(item) for item in allowed}
        environments = [env for env in environments if int(env["id"]) in allowed_set]
    app["environments"] = environments
    return app, 200


def update_app(app_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    payload = dict(data or {})
    name = str(payload.get("name") or "").strip()
    if not name:
        current = applications_repository.fetch_application(app_id)
        if not current:
            return {"error": "Application not found."}, 404
        name = str(current.get("name") or "")
    extra = {
        key: payload.get(key, "")
        for key in (
            "owner",
            "data_class",
            "roe_link",
            "cookie_domain",
            "idp",
            "token_audience",
            "app_lead",
        )
        if key in payload
    }
    try:
        exists = applications_repository.update_application(app_id, name, extra_fields=extra)
    except IntegrityError:
        return {"error": "Application name already exists."}, 409
    if not exists:
        return {"error": "Application not found."}, 404
    return get_app(app_id)


def list_environments(app_id: int, username: str = "", role: str = "") -> Tuple[Dict[str, Any], int]:
    payload, status = get_app(app_id, username=username, role=role)
    if status != 200:
        return payload, status
    return {"environments": payload.get("environments") or []}, 200


def create_environment(app_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    try:
        env = environments_repository.create_environment(app_id, data or {})
    except ValueError:
        return {"error": "slug and display_name are required."}, 400
    except IntegrityError:
        return {"error": "Environment slug already exists for this application."}, 409
    return {"environment": env}, 201


def delete_environment(app_id: int, env_id: int) -> Tuple[Dict[str, Any], int]:
    result = environments_repository.delete_environment(app_id, env_id)
    if result == "not_found":
        return {"error": "Environment not found."}, 404
    if result == "protected":
        return {"error": "Unassigned cannot be deleted. It is the filing bucket for hosts with no environment."}, 409
    if result == "in_use":
        return {"error": "Environment is in use. Move or unfile its hosts first."}, 409
    return {"message": "Environment deleted."}, 200


def update_environment(app_id: int, env_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    payload = dict(data or {})
    if "max_concurrent_scans" in payload:
        try:
            ceiling = int(payload["max_concurrent_scans"])
        except (TypeError, ValueError):
            return {"error": "max_concurrent_scans must be an integer."}, 400
        if ceiling < 1 or ceiling > 10:
            return {"error": "max_concurrent_scans must be between 1 and 10."}, 400
        payload["max_concurrent_scans"] = ceiling
    updated = environments_repository.update_environment(app_id, env_id, payload)
    if not updated:
        return {"error": "Environment not found."}, 404
    env = environments_repository.fetch_environment(app_id, env_id)
    return {"environment": env}, 200


def assign_hosts(app_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    record_ids = data.get("record_ids") or []
    if not isinstance(record_ids, list) or not record_ids:
        return {"error": "record_ids is required."}, 400
    try:
        environment_id = int(data.get("environment_id"))
    except (TypeError, ValueError):
        return {"error": "environment_id is required."}, 400
    in_scope = data.get("in_scope")
    try:
        ids = [int(item) for item in record_ids]
    except (TypeError, ValueError):
        return {"error": "record_ids must be integers."}, 400
    try:
        updated = applications_repository.assign_hosts(
            app_id, ids, environment_id, in_scope if in_scope is None else bool(in_scope)
        )
    except ValueError:
        return {"error": "Environment not found."}, 404
    return {"updated": updated}, 200


def assign_host_testers(
    app_id: int,
    data: Dict[str, Any],
    username: str = "",
    role: str = "",
) -> Tuple[Dict[str, Any], int]:
    record_ids = data.get("record_ids") or []
    requested = str((data or {}).get("username") or "").strip()
    actor = str(username or "").strip()
    if not requested:
        return {"error": "username is required."}, 400
    if actor and requested.lower() != actor.lower():
        if not user_has_permission(actor, role, "reassign_pentests_admin"):
            return {"error": "Assigning another tester requires reassign_pentests_admin."}, 403
    if not isinstance(record_ids, list) or not record_ids:
        return {"error": "record_ids is required."}, 400
    try:
        ids = [int(item) for item in record_ids]
    except (TypeError, ValueError):
        return {"error": "record_ids must be integers."}, 400
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    from app.config import DB_PATH
    from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        placeholders = ",".join("?" for _ in ids)
        c.execute(
            f"SELECT id FROM records WHERE application_id = ? AND id IN ({placeholders})",
            tuple([app_id, *ids]),
        )
        owned = [int(row["id"] if isinstance(row, dict) else row[0]) for row in c.fetchall() or []]
    if not owned:
        return {"error": "No matching hosts in this application."}, 404
    allowed_envs = _acl_env_ids(app_id, actor, role)
    for record_id in owned:
        host = fetch_record_by_id(record_id) or {}
        env_id = host.get("environment_id")
        if env_id and _deny_env(allowed_envs, env_id):
            return {"error": "Environment is not visible to this user."}, 403
    updated = phase2b_repository.assign_record_testers(owned, requested)
    synced = set()
    for record_id in owned:
        env = phase2b_repository.fetch_host_env(record_id)
        env_id = env.get("id") if env else None
        if not env_id:
            continue
        wave = phase2b_repository.find_open_wave_for_env(app_id, int(env_id))
        if wave and int(wave["id"]) not in synced:
            phase2b_repository.sync_wave_host_collaborators(int(wave["id"]))
            synced.add(int(wave["id"]))
    return {"updated": updated, "tested_by": requested}, 200


def list_hosts(app_id: int, args: Dict[str, Any], username: str = "", role: str = "") -> Tuple[Dict[str, Any], int]:
    from app.config import DB_PATH
    from app.integrations.db.connection import ROW_AS_DICT, get_db_connection, get_table_columns

    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    limit, offset = _page(args.get("limit"), args.get("offset"))
    query = str(args.get("q") or "").strip().lower()
    env_id = args.get("env_id")
    in_scope = args.get("in_scope")
    allowed = _acl_env_ids(app_id, username, role)
    filters = ["r.application_id = ?"]
    params: List[Any] = [app_id]
    parsed_env_id = None
    if env_id not in (None, "", "null"):
        try:
            parsed_env_id = int(env_id)
        except (TypeError, ValueError):
            return {"error": "Invalid env_id."}, 400
        if _deny_env(allowed, parsed_env_id):
            return {"error": "Environment is not visible to this user."}, 403
        filters.append("r.environment_id = ?")
        params.append(parsed_env_id)
    elif allowed is not None:
        if not allowed:
            return {"hosts": [], "total": 0, "limit": limit, "offset": offset}, 200
        placeholders = ",".join("?" for _ in allowed)
        filters.append(f"r.environment_id IN ({placeholders})")
        params.extend(allowed)
    if str(in_scope).lower() in {"1", "true", "yes"}:
        filters.append("COALESCE(r.in_scope, FALSE) = TRUE")
    elif str(in_scope).lower() in {"0", "false", "no"}:
        filters.append("COALESCE(r.in_scope, FALSE) = FALSE")
    if query:
        filters.append("LOWER(r.name) LIKE ?")
        params.append(f"%{query}%")
    where_sql = " AND ".join(filters)
    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        pentest_cols = get_table_columns(c, "pentest_data")
        occ_cols = get_table_columns(c, "finding_occurrences")
        scan_sql = (
            ", COALESCE(p.scan_status, 'idle') AS scan_status"
            if "scan_status" in pentest_cols
            else ", 'idle' AS scan_status"
        )
        occ_sql = (
            """,
                (SELECT COUNT(*) FROM finding_occurrences o WHERE o.record_id = r.id) AS finding_count,
                (SELECT COUNT(*) FROM finding_occurrences o
                 WHERE o.record_id = r.id AND o.status IN ('open', 'draft', 'retest')) AS open_occurrence_count
            """
            if "record_id" in occ_cols
            else ", 0 AS finding_count, 0 AS open_occurrence_count"
        )
        c.execute(f"SELECT COUNT(*) AS n FROM records r WHERE {where_sql}", tuple(params))
        total = int((c.fetchone() or {}).get("n") or 0)
        c.execute(
            f"""
            SELECT
                r.id, r.name, r.ip_address, r.status, r.in_scope, r.environment_id,
                r.env_suggestion, e.slug AS environment_slug, e.display_name AS environment_name,
                COALESCE(p.status, 'Not Started') AS pentest_status,
                COALESCE(p.tested_by, '') AS tested_by
                {scan_sql}
                {occ_sql}
            FROM records r
            LEFT JOIN environments e ON e.id = r.environment_id
            LEFT JOIN pentest_data p ON p.record_id = r.id
            WHERE {where_sql}
            ORDER BY r.name
            LIMIT ? OFFSET ?
            """,
            tuple([*params, limit, offset]),
        )
        hosts = [dict(row) for row in c.fetchall() or []]
    for host in hosts:
        if not host.get("env_suggestion"):
            host["env_suggestion"] = suggest_env_slug(host.get("name") or "")
    return {"hosts": hosts, "total": total, "limit": limit, "offset": offset}, 200


def list_findings(app_id: int, args: Dict[str, Any], username: str = "", role: str = "") -> Tuple[Dict[str, Any], int]:
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    limit, offset = _page(args.get("limit"), args.get("offset"))
    env_id = None
    if args.get("env_id") not in (None, "", "null"):
        try:
            env_id = int(args.get("env_id"))
        except (TypeError, ValueError):
            return {"error": "Invalid env_id."}, 400
    allowed = _acl_env_ids(app_id, username, role)
    if _deny_env(allowed, env_id):
        return {"error": "Environment is not visible to this user."}, 403
    include_drafts = str(args.get("include_drafts") or "1").lower() not in {"0", "false", "no"}
    severity_floor = None
    if args.get("severity_floor") not in (None, "", "null"):
        try:
            severity_floor = float(args.get("severity_floor"))
        except (TypeError, ValueError):
            return {"error": "Invalid severity_floor."}, 400
    findings, total = pentest_findings_repository.fetch_app_findings(
        app_id,
        env_id=env_id,
        env_ids=allowed,
        status=str(args.get("status") or "") or None,
        include_drafts=include_drafts,
        severity_floor=severity_floor,
        limit=limit,
        offset=offset,
    )
    return {"findings": findings, "total": total, "limit": limit, "offset": offset}, 200


def create_finding(
    app_id: int, data: Dict[str, Any], username: str, role: str = ""
) -> Tuple[Dict[str, Any], int]:
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    try:
        record_id = int(data.get("record_id"))
    except (TypeError, ValueError):
        return {"error": "record_id (found-here host) is required."}, 400
    record = fetch_record_by_id(record_id)
    if not record:
        return {"error": "Host not found."}, 404
    if int(record.get("application_id") or 0) != int(app_id):
        return {"error": "Host is not in this application."}, 400
    denied = _host_access_error(record_id, username, role, "create a finding on")
    if denied:
        return denied
    extra_ids = data.get("record_ids") or []
    parsed_extra = []
    if isinstance(extra_ids, list) and extra_ids:
        try:
            parsed_extra = [int(item) for item in extra_ids if str(item).isdigit() or isinstance(item, int)]
        except (TypeError, ValueError):
            return {"error": "record_ids must be integers."}, 400
        for extra_id in parsed_extra:
            extra_denied = _host_access_error(extra_id, username, role, "attach a finding to")
            if extra_denied:
                return extra_denied
    payload = dict(data)
    payload["created_by"] = username
    payload["application_id"] = app_id
    payload.setdefault("status", "open")
    payload.setdefault("source", "human")
    wave_id = data.get("wave_id") or data.get("discovered_wave_id")
    if wave_id in (None, "", 0):
        env_id = record.get("environment_id")
        if env_id:
            open_wave = phase2b_repository.find_open_wave_for_env(app_id, int(env_id))
            if open_wave:
                wave_id = open_wave.get("id")
    if wave_id not in (None, "", 0):
        _wave, blocked = _require_open_wave(app_id, wave_id)
        if blocked:
            return blocked
        payload["discovered_wave_id"] = int(wave_id)
        wave_id = int(wave_id)
    else:
        wave_id = None
    finding_id = pentest_findings_repository.insert_finding(record_id, payload)
    collaborators = {username}
    if wave_id:
        collaborators.update(phase2b_repository.list_wave_members(wave_id))
    if isinstance(data.get("collaborators"), list):
        collaborators.update(str(name).strip() for name in data["collaborators"] if str(name).strip())
    pentest_findings_repository.replace_finding_collaborators(finding_id, list(collaborators))
    finding = pentest_findings_repository.get_finding(finding_id)
    if parsed_extra:
        pentest_findings_repository.attach_occurrences(finding_id, parsed_extra)
        finding = pentest_findings_repository.get_finding(finding_id)
    return {"finding": finding}, 201


def get_finding(finding_id: str, username: str = "", role: str = "") -> Tuple[Dict[str, Any], int]:
    finding = pentest_findings_repository.get_finding(finding_id)
    if not finding:
        return {"error": "Finding not found."}, 404
    denied = _finding_host_access_error(finding, username, role, "view")
    if denied:
        return denied
    found_here = fetch_record_by_id(finding.get("record_id"))
    if found_here and found_here.get("application_id") and found_here.get("environment_id"):
        if _deny_env(
            _acl_env_ids(int(found_here["application_id"]), username, role),
            int(found_here["environment_id"]),
        ):
            return {"error": "Environment is not visible to this user."}, 403
    environment = None
    wave = None
    app_id = finding.get("application_id")
    if found_here and found_here.get("environment_id") and app_id:
        environment = environments_repository.fetch_environment(int(app_id), int(found_here["environment_id"]))
    if finding.get("discovered_wave_id"):
        candidate = phase2b_repository.get_wave(int(finding["discovered_wave_id"]))
        if candidate and int(candidate.get("application_id") or 0) == int(app_id or 0):
            wave = candidate
    host = None
    if found_here:
        host = {
            "id": found_here.get("id"),
            "name": found_here.get("name"),
            "ip_address": found_here.get("ip_address"),
            "environment_id": found_here.get("environment_id"),
        }
    return {
        "finding": finding,
        "found_here": host,
        "environment": environment,
        "wave": wave,
    }, 200


def patch_finding(
    finding_id: str, data: Dict[str, Any], username: str = "", role: str = ""
) -> Tuple[Dict[str, Any], int]:
    current = pentest_findings_repository.get_finding(finding_id)
    if not current:
        return {"error": "Finding not found."}, 404
    denied = _finding_host_access_error(current, username, role, "modify")
    if denied:
        return denied
    blocked = _reject_closed_finding_wave(current)
    if blocked:
        return blocked
    finding = pentest_findings_repository.update_finding_fields(finding_id, data or {})
    if not finding:
        return {"error": "Finding not found."}, 404
    return {"finding": finding}, 200


def add_occurrences(
    finding_id: str, data: Dict[str, Any], username: str = "", role: str = ""
) -> Tuple[Dict[str, Any], int]:
    current = pentest_findings_repository.get_finding(finding_id)
    if not current:
        return {"error": "Finding not found."}, 404
    denied = _finding_host_access_error(current, username, role, "modify")
    if denied:
        return denied
    blocked = _reject_closed_finding_wave(current)
    if blocked:
        return blocked
    record_ids = data.get("record_ids") or []
    if not isinstance(record_ids, list) or not record_ids:
        return {"error": "record_ids is required."}, 400
    try:
        ids = [int(item) for item in record_ids]
    except (TypeError, ValueError):
        return {"error": "record_ids must be integers."}, 400
    for extra_id in ids:
        extra_denied = _host_access_error(extra_id, username, role, "attach a finding to")
        if extra_denied:
            return extra_denied
    finding = pentest_findings_repository.attach_occurrences(finding_id, ids)
    if not finding:
        return {"error": "Finding not found."}, 404
    return {"finding": finding}, 200


def patch_occurrence(
    finding_id: str, record_id: int, data: Dict[str, Any], username: str = "", role: str = ""
) -> Tuple[Dict[str, Any], int]:
    status = str((data or {}).get("status") or "").strip()
    if not status:
        return {"error": "status is required."}, 400
    cleaned = status.lower()
    if cleaned not in pentest_findings_repository.OCCURRENCE_STATUSES:
        allowed = ", ".join(sorted(pentest_findings_repository.OCCURRENCE_STATUSES))
        return {"error": f"status must be one of: {allowed}."}, 400
    current = pentest_findings_repository.get_finding(finding_id)
    if not current:
        return {"error": "Occurrence not found."}, 404
    denied = _finding_host_access_error(current, username, role, "modify")
    if denied:
        return denied
    occ_denied = _host_access_error(record_id, username, role, "modify")
    if occ_denied:
        return occ_denied
    blocked = _reject_closed_finding_wave(current)
    if blocked:
        return blocked
    try:
        finding = pentest_findings_repository.set_occurrence_status(finding_id, record_id, cleaned)
    except ValueError:
        allowed = ", ".join(sorted(pentest_findings_repository.OCCURRENCE_STATUSES))
        return {"error": f"status must be one of: {allowed}."}, 400
    if not finding:
        return {"error": "Occurrence not found."}, 404
    return {"finding": finding}, 200


def bulk_set_occurrence_status(
    app_id: int, data: Dict[str, Any], username: str = "", role: str = ""
) -> Tuple[Dict[str, Any], int]:
    if not applications_repository.fetch_application(app_id):
        return {"error": "Application not found."}, 404
    payload = data or {}
    to_status = str(payload.get("to_status") or "retest").strip()
    from_statuses = payload.get("from_statuses")
    if from_statuses is not None and not isinstance(from_statuses, list):
        return {"error": "from_statuses must be a list."}, 400
    try:
        env_ids = [int(item) for item in (payload.get("env_ids") or [])]
        record_ids = [int(item) for item in (payload.get("record_ids") or [])]
    except (TypeError, ValueError):
        return {"error": "env_ids and record_ids must be integers."}, 400
    allowed_envs = _acl_env_ids(app_id, username, role)
    if env_ids:
        if any(_deny_env(allowed_envs, env_id) for env_id in env_ids):
            return {"error": "Environment is not visible to this user."}, 403
    elif allowed_envs is not None:
        env_ids = list(allowed_envs)
        if not env_ids:
            return {"updated": 0, "to_status": to_status.strip().lower()}, 200
    for record_id in record_ids:
        denied = _host_access_error(record_id, username, role, "modify")
        if denied:
            return denied
    try:
        updated = pentest_findings_repository.bulk_set_occurrence_status(
            app_id,
            to_status,
            from_statuses=from_statuses,
            env_ids=env_ids or None,
            record_ids=record_ids or None,
        )
    except ValueError:
        allowed = ", ".join(sorted(pentest_findings_repository.OCCURRENCE_STATUSES))
        return {"error": f"status must be one of: {allowed}."}, 400
    return {"updated": updated, "to_status": to_status.strip().lower()}, 200


def merge_findings(
    finding_id: str, data: Dict[str, Any], username: str = "", role: str = ""
) -> Tuple[Dict[str, Any], int]:
    loser_id = str(data.get("loser_id") or "").strip()
    if not loser_id:
        return {"error": "loser_id is required."}, 400
    survivor = pentest_findings_repository.get_finding(finding_id)
    if not survivor:
        return {"error": "Finding not found."}, 404
    loser = pentest_findings_repository.get_finding(loser_id)
    if not loser:
        return {"error": "Finding not found."}, 404
    denied = _finding_host_access_error(survivor, username, role, "merge") or _finding_host_access_error(
        loser, username, role, "merge"
    )
    if denied:
        return denied
    blocked = _reject_closed_finding_wave(survivor) or _reject_closed_finding_wave(loser)
    if blocked:
        return blocked
    finding = pentest_findings_repository.merge_findings(finding_id, loser_id)
    if not finding:
        return {"error": "Finding not found."}, 404
    return {"finding": finding}, 200


def promote_finding(
    finding_id: str, data: Dict[str, Any], username: str = "", role: str = ""
) -> Tuple[Dict[str, Any], int]:
    current = pentest_findings_repository.get_finding(finding_id)
    if not current:
        return {"error": "Finding not found."}, 404
    denied = _finding_host_access_error(current, username, role, "promote")
    if denied:
        return denied
    blocked = _reject_closed_finding_wave(current)
    if blocked:
        return blocked
    candidates = data.get("candidate_record_ids") or []
    ids = []
    if isinstance(candidates, list):
        try:
            ids = [int(item) for item in candidates]
        except (TypeError, ValueError):
            return {"error": "candidate_record_ids must be integers."}, 400
    for extra_id in ids:
        extra_denied = _host_access_error(extra_id, username, role, "promote a finding onto")
        if extra_denied:
            return extra_denied
    finding = pentest_findings_repository.promote_finding(finding_id, ids)
    if not finding:
        return {"error": "Finding not found."}, 404
    return {"finding": finding}, 200


def _host_visible_for_search(host: Dict[str, Any], username: str, role: str, cache: Dict[int, Optional[List[int]]]) -> bool:
    app_id = host.get("application_id")
    env_id = host.get("environment_id")
    if not app_id or not env_id:
        return True
    app_key = int(app_id)
    if app_key not in cache:
        cache[app_key] = _acl_env_ids(app_key, username, role)
    allowed = cache[app_key]
    return not _deny_env(allowed, int(env_id))


def search_hosts(
    args: Dict[str, Any], username: str = "", role: str = ""
) -> Tuple[Dict[str, Any], int]:
    from app.config import DB_PATH
    from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

    query = str(args.get("q") or "").strip().lower()
    if not query:
        return {"hosts": [], "total": 0, "limit": 20, "offset": 0}, 200
    limit, offset = _page(args.get("limit") or 20, args.get("offset"))
    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT
                r.id, r.name, r.ip_address, r.application_id, r.environment_id,
                a.name AS application_name, e.slug AS environment_slug,
                e.display_name AS environment_name
            FROM records r
            LEFT JOIN applications a ON a.id = r.application_id
            LEFT JOIN environments e ON e.id = r.environment_id
            WHERE LOWER(r.name) LIKE ?
            ORDER BY r.name
            """,
            (f"%{query}%",),
        )
        hosts = [dict(row) for row in c.fetchall() or []]
    cache: Dict[int, Optional[List[int]]] = {}
    visible = [host for host in hosts if _host_visible_for_search(host, username, role, cache)]
    total = len(visible)
    page = visible[offset : offset + limit]
    return {"hosts": page, "total": total, "limit": limit, "offset": offset}, 200
