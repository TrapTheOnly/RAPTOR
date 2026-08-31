from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.domain.integrations import fields as field_domain
from app.integrations.defectdojo.client import DefectDojoClient, DefectDojoError
from app.integrations.jira.client import JiraClient, JiraError
from app.integrations.secrets import decrypt_secret, encrypt_secret, has_secret
from app.repositories import applications_repository, integrations_repository, pentest_findings_repository
from app.services import app_program_service, phase2b_service

logger = logging.getLogger(__name__)


def _public_connection(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "name": row["name"],
        "base_url": row["base_url"],
        "auth_type": row.get("auth_type") or "api_token",
        "auth_email": row.get("auth_email") or "",
        "has_secret": has_secret(row.get("secret_ciphertext")),
        "extra": row.get("extra") or {},
        "status": row.get("status") or "draft",
        "last_error": row.get("last_error") or "",
        "created_by": row.get("created_by") or "",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }


def _public_template(row: Dict[str, Any], mappings: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    payload = {
        "id": row["id"],
        "connection_id": row["connection_id"],
        "name": row["name"],
        "external_project_key": row.get("external_project_key") or "",
        "external_project_name": row.get("external_project_name") or "",
        "issue_type_id": row.get("issue_type_id") or "",
        "issue_type_name": row.get("issue_type_name") or "",
        "extra": row.get("extra") or {},
        "is_default": bool(row.get("is_default")),
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }
    if mappings is not None:
        payload["mappings"] = mappings
    return payload


def catalog() -> Tuple[Dict[str, Any], int]:
    return field_domain.catalog(), 200


def list_connections(kind: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
    rows = integrations_repository.list_connections(kind=kind)
    return {"connections": [_public_connection(row) for row in rows]}, 200


def get_connection(connection_id: int) -> Tuple[Dict[str, Any], int]:
    row = integrations_repository.get_connection(connection_id)
    if not row:
        return {"error": "Integration not found."}, 404
    templates = [
        _public_template(item, integrations_repository.list_mappings(item["id"]))
        for item in integrations_repository.list_templates(connection_id)
    ]
    return {"connection": _public_connection(row), "templates": templates}, 200


def _normalize_kind(value: Any) -> Optional[str]:
    kind = str(value or "").strip().lower()
    return kind if kind in {"jira", "defectdojo"} else None


def create_connection(data: Dict[str, Any], username: str) -> Tuple[Dict[str, Any], int]:
    kind = _normalize_kind((data or {}).get("kind"))
    if not kind:
        return {"error": "kind must be jira or defectdojo."}, 400
    base_url = str((data or {}).get("base_url") or "").strip()
    token = str((data or {}).get("api_token") or (data or {}).get("secret") or "").strip()
    if not base_url:
        return {"error": "base_url is required."}, 400
    if not token:
        return {"error": "API key is required."}, 400
    name = str((data or {}).get("name") or "").strip() or ("Jira" if kind == "jira" else "DefectDojo")
    auth_type = str((data or {}).get("auth_type") or "api_token").strip() or "api_token"
    auth_email = str((data or {}).get("auth_email") or (data or {}).get("email") or "").strip()
    if kind == "jira" and auth_type != "pat" and not auth_email:
        return {"error": "Jira email is required for API token auth."}, 400
    row = integrations_repository.insert_connection(
        {
            "kind": kind,
            "name": name,
            "base_url": base_url,
            "auth_type": auth_type,
            "auth_email": auth_email,
            "secret_ciphertext": encrypt_secret(token),
            "extra": (data or {}).get("extra") if isinstance((data or {}).get("extra"), dict) else {},
            "status": "draft",
            "created_by": username,
        }
    )
    tested, status = test_connection(int(row["id"]))
    if status != 200:
        return {"connection": _public_connection(integrations_repository.get_connection(row["id"])), **tested}, status
    return {"connection": tested["connection"], "identity": tested.get("identity")}, 201


def update_connection(connection_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    row = integrations_repository.get_connection(connection_id)
    if not row:
        return {"error": "Integration not found."}, 404
    fields: Dict[str, Any] = {}
    for key in ("name", "base_url", "auth_type", "auth_email"):
        if key in (data or {}):
            fields[key] = str((data or {}).get(key) or "").strip()
    if "email" in (data or {}) and "auth_email" not in fields:
        fields["auth_email"] = str((data or {}).get("email") or "").strip()
    token = str((data or {}).get("api_token") or (data or {}).get("secret") or "").strip()
    if token and token not in {"••••••••", "********"}:
        fields["secret_ciphertext"] = encrypt_secret(token)
    if "extra" in (data or {}) and isinstance((data or {}).get("extra"), dict):
        fields["extra"] = data["extra"]
    updated = integrations_repository.update_connection(connection_id, fields)
    return {"connection": _public_connection(updated or row)}, 200


def delete_connection(connection_id: int) -> Tuple[Dict[str, Any], int]:
    if not integrations_repository.get_connection(connection_id):
        return {"error": "Integration not found."}, 404
    integrations_repository.delete_connection(connection_id)
    return {"ok": True}, 200


def _client_for(row: Dict[str, Any]):
    token = decrypt_secret(row.get("secret_ciphertext"))
    if not token:
        raise ValueError("This integration has no API key yet.")
    if row["kind"] == "jira":
        return JiraClient(
            row["base_url"],
            token,
            email=row.get("auth_email") or "",
            auth_type=row.get("auth_type") or "api_token",
            api_style="auto",
        )
    return DefectDojoClient(row["base_url"], token)


def test_connection(connection_id: int) -> Tuple[Dict[str, Any], int]:
    row = integrations_repository.get_connection(connection_id)
    if not row:
        return {"error": "Integration not found."}, 404
    try:
        client = _client_for(row)
    except ValueError as exc:
        return {"error": str(exc)}, 400
    try:
        identity = client.myself()
        extra = dict(row.get("extra") or {})
        if row["kind"] == "jira" and hasattr(client, "api_style"):
            extra["api_style"] = getattr(client, "api_style")
        integrations_repository.update_connection(
            connection_id,
            {"status": "connected", "last_error": "", "extra": extra},
        )
        display = identity.get("displayName") or identity.get("username") or identity.get("email") or "connected"
        return {
            "connection": _public_connection(integrations_repository.get_connection(connection_id)),
            "identity": {"name": display, "raw": {k: identity.get(k) for k in ("accountId", "id", "username", "email")}},
        }, 200
    except (JiraError, DefectDojoError, ValueError) as exc:
        integrations_repository.update_connection(connection_id, {"status": "error", "last_error": str(exc)})
        return {"error": str(exc), "connection": _public_connection(integrations_repository.get_connection(connection_id))}, 400
    finally:
        try:
            client.close()
        except Exception:
            pass


def list_catalog(connection_id: int, resource: str, args: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    row = integrations_repository.get_connection(connection_id)
    if not row:
        return {"error": "Integration not found."}, 404
    try:
        client = _client_for(row)
    except ValueError as exc:
        return {"error": str(exc)}, 400
    try:
        if row["kind"] == "jira":
            if resource == "projects":
                return {"projects": client.list_projects()}, 200
            if resource == "issue-types":
                return {"issue_types": client.list_issue_types(str(args.get("project") or ""))}, 200
            if resource == "fields":
                raw = client.get_create_fields(str(args.get("project") or ""), str(args.get("issue_type") or ""))
                return {"fields": field_domain.parse_jira_fields(raw)}, 200
            return {"error": "Unknown Jira catalog resource."}, 400
        if resource == "products":
            return {"products": client.list_products()}, 200
        if resource == "engagements":
            return {"engagements": client.list_engagements(str(args.get("product") or ""))}, 200
        if resource == "tests":
            return {"tests": client.list_tests(str(args.get("engagement") or ""))}, 200
        if resource == "fields":
            return {"fields": field_domain.defectdojo_fields()}, 200
        return {"error": "Unknown DefectDojo catalog resource."}, 400
    except (JiraError, DefectDojoError, ValueError) as exc:
        return {"error": str(exc)}, 400
    finally:
        try:
            client.close()
        except Exception:
            pass


def list_templates(connection_id: int) -> Tuple[Dict[str, Any], int]:
    if not integrations_repository.get_connection(connection_id):
        return {"error": "Integration not found."}, 404
    templates = [
        _public_template(item, integrations_repository.list_mappings(item["id"]))
        for item in integrations_repository.list_templates(connection_id)
    ]
    return {"templates": templates}, 200


def create_template(connection_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    row = integrations_repository.get_connection(connection_id)
    if not row:
        return {"error": "Integration not found."}, 404
    name = str((data or {}).get("name") or "").strip()
    extra = (data or {}).get("extra") if isinstance((data or {}).get("extra"), dict) else {}
    if row["kind"] == "jira":
        project_key = str((data or {}).get("external_project_key") or (data or {}).get("project") or "").strip()
        issue_type_id = str((data or {}).get("issue_type_id") or (data or {}).get("issue_type") or "").strip()
        if not project_key or not issue_type_id:
            return {"error": "Select a Jira project and issue type."}, 400
        client = None
        try:
            client = _client_for(row)
            fields = field_domain.parse_jira_fields(client.get_create_fields(project_key, issue_type_id))
        except (JiraError, ValueError) as exc:
            return {"error": str(exc)}, 400
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
        name = name or f"{(data or {}).get('external_project_name') or project_key} / {(data or {}).get('issue_type_name') or issue_type_id}"
        template = integrations_repository.insert_template(
            {
                "connection_id": connection_id,
                "name": name,
                "external_project_key": project_key,
                "external_project_name": str((data or {}).get("external_project_name") or project_key),
                "issue_type_id": issue_type_id,
                "issue_type_name": str((data or {}).get("issue_type_name") or issue_type_id),
                "extra": extra,
                "is_default": bool((data or {}).get("is_default"))
                or not integrations_repository.list_templates(connection_id),
            }
        )
    else:
        product_id = str((data or {}).get("external_project_key") or extra.get("product_id") or "").strip()
        if not product_id:
            return {"error": "Select a DefectDojo product."}, 400
        extra = {
            **extra,
            "product_id": product_id,
            "product_name": str((data or {}).get("external_project_name") or extra.get("product_name") or product_id),
            "engagement_id": str(extra.get("engagement_id") or (data or {}).get("engagement_id") or ""),
            "engagement_mode": str(extra.get("engagement_mode") or (data or {}).get("engagement_mode") or "per_wave"),
            "test_id": str(extra.get("test_id") or (data or {}).get("test_id") or ""),
            "test_mode": str(extra.get("test_mode") or (data or {}).get("test_mode") or "create"),
            "test_title": str(extra.get("test_title") or "RAPTOR"),
        }
        fields = field_domain.defectdojo_fields()
        name = name or extra["product_name"]
        template = integrations_repository.insert_template(
            {
                "connection_id": connection_id,
                "name": name,
                "external_project_key": product_id,
                "external_project_name": extra["product_name"],
                "issue_type_id": extra.get("engagement_id") or "",
                "issue_type_name": extra.get("engagement_mode") or "per_wave",
                "extra": extra,
                "is_default": bool((data or {}).get("is_default"))
                or not integrations_repository.list_templates(connection_id),
            }
        )
    mappings = field_domain.seed_mappings(row["kind"], fields)
    saved = integrations_repository.replace_mappings(int(template["id"]), mappings)
    return {"template": _public_template(template, saved)}, 201


def update_template(connection_id: int, template_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    template = integrations_repository.get_template(template_id)
    if not template or int(template["connection_id"]) != int(connection_id):
        return {"error": "Template not found."}, 404
    fields: Dict[str, Any] = {}
    for key in (
        "name",
        "external_project_key",
        "external_project_name",
        "issue_type_id",
        "issue_type_name",
        "is_default",
    ):
        if key in (data or {}):
            fields[key] = (data or {}).get(key)
    extra = dict(template.get("extra") or {})
    if isinstance((data or {}).get("extra"), dict):
        extra.update(data["extra"])
        fields["extra"] = extra
    updated = integrations_repository.update_template(template_id, fields)
    mappings = integrations_repository.list_mappings(template_id)
    if (data or {}).get("refresh_fields"):
        refreshed, status = refresh_template_fields(connection_id, template_id)
        if status != 200:
            return refreshed, status
        return refreshed, 200
    return {"template": _public_template(updated or template, mappings)}, 200


def delete_template(connection_id: int, template_id: int) -> Tuple[Dict[str, Any], int]:
    template = integrations_repository.get_template(template_id)
    if not template or int(template["connection_id"]) != int(connection_id):
        return {"error": "Template not found."}, 404
    integrations_repository.delete_template(template_id)
    return {"ok": True}, 200


def refresh_template_fields(connection_id: int, template_id: int) -> Tuple[Dict[str, Any], int]:
    row = integrations_repository.get_connection(connection_id)
    template = integrations_repository.get_template(template_id)
    if not row or not template or int(template["connection_id"]) != int(connection_id):
        return {"error": "Template not found."}, 404
    try:
        if row["kind"] == "jira":
            client = _client_for(row)
            live = field_domain.parse_jira_fields(
                client.get_create_fields(template["external_project_key"], template["issue_type_id"])
            )
            client.close()
        else:
            live = field_domain.defectdojo_fields()
    except (JiraError, DefectDojoError, ValueError) as exc:
        return {"error": str(exc)}, 400
    merged = field_domain.merge_mappings(live, integrations_repository.list_mappings(template_id), row["kind"])
    saved = integrations_repository.replace_mappings(template_id, merged)
    return {"template": _public_template(template, saved), "fields": live}, 200


def save_mappings(connection_id: int, template_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    template = integrations_repository.get_template(template_id)
    if not template or int(template["connection_id"]) != int(connection_id):
        return {"error": "Template not found."}, 404
    incoming = (data or {}).get("mappings")
    if not isinstance(incoming, list):
        return {"error": "mappings must be a list."}, 400
    cleaned = []
    for index, item in enumerate(incoming):
        if not isinstance(item, dict) or not item.get("external_field_id"):
            continue
        mode = str(item.get("fill_mode") or "ask")
        if mode not in {"mapped", "ask", "static", "skip"}:
            mode = "ask"
        raptor_ids = field_domain.parse_raptor_fields(item.get("raptor_field"))
        cleaned.append(
            {
                "raptor_field": field_domain.join_raptor_fields(raptor_ids) if raptor_ids else "",
                "external_field_id": str(item["external_field_id"]),
                "external_field_name": str(item.get("external_field_name") or ""),
                "external_field_type": str(item.get("external_field_type") or "string"),
                "fill_mode": mode,
                "static_value": item.get("static_value") or "",
                "required": bool(item.get("required")),
                "allowed_values": item.get("allowed_values") if isinstance(item.get("allowed_values"), list) else [],
                "sort_order": item.get("sort_order", index),
            }
        )
    saved = integrations_repository.replace_mappings(template_id, cleaned)
    return {"template": _public_template(template, saved)}, 200


def list_ready(kind: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
    connections = []
    for row in integrations_repository.list_connections(kind=kind):
        if row.get("status") != "connected":
            continue
        templates = [
            _public_template(item)
            for item in integrations_repository.list_templates(int(row["id"]))
        ]
        if not templates:
            continue
        connections.append({**_public_connection(row), "templates": templates})
    connections.sort(key=lambda item: (not any(tmpl.get("is_default") for tmpl in item["templates"]), item["id"]))
    return {"connections": connections}, 200


def _load_finding_context(finding_id: str) -> Optional[Dict[str, Any]]:
    payload, status = app_program_service.get_finding(str(finding_id))
    if status != 200:
        return None
    finding = payload.get("finding") or {}
    try:
        from app.integrations.reporting.report_context import hydrate_finding_fields

        finding = hydrate_finding_fields(finding)
    except Exception:
        pass
    application = None
    if finding.get("application_id"):
        application = applications_repository.fetch_application(int(finding["application_id"]))
    return {
        "finding": finding,
        "found_here": payload.get("found_here"),
        "environment": payload.get("environment"),
        "wave": payload.get("wave"),
        "application": application or {},
    }


def _latest_export(finding_id: str, kind: str) -> Optional[Dict[str, Any]]:
    rows = integrations_repository.list_exports_for_findings([finding_id], kind=kind)
    return rows[0] if rows else None


def _http_ticket_url(finding: Optional[Dict[str, Any]]) -> str:
    value = str((finding or {}).get("ticket_url") or "").strip()
    return value if value.lower().startswith(("http://", "https://")) else ""


def _already_at_destination(kind: str, finding: Dict[str, Any], existing: Optional[Dict[str, Any]]) -> bool:
    if kind == "jira":
        return bool(_http_ticket_url(finding))
    return bool(existing)


def preview_export(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    template, connection, error = _resolve_template(data)
    if error:
        return error
    finding_ids = _finding_ids_from_request(data)
    if not finding_ids:
        return {"error": "Select at least one finding."}, 400
    mappings = integrations_repository.list_mappings(int(template["id"]))
    live_mappings, refresh_error = _refresh_allowed_values(connection, template, mappings)
    mappings = live_mappings
    items = []
    sample_values = None
    for finding_id in finding_ids:
        context = _load_finding_context(finding_id)
        if not context:
            items.append({"id": finding_id, "error": "Finding not found."})
            continue
        values = field_domain.raptor_values(context)
        if sample_values is None:
            sample_values = values
        existing = _latest_export(str(context["finding"]["id"]), connection["kind"])
        already = _already_at_destination(connection["kind"], context["finding"], existing)
        items.append(
            {
                "id": context["finding"]["id"],
                "title": values["title"],
                "severity": values["severity_label"],
                "status": values["status"],
                "already_exported": already,
                "existing_url": _http_ticket_url(context["finding"]) or (existing or {}).get("external_url") or "",
                "existing_id": (existing or {}).get("external_id") or "",
            }
        )
    mapped_preview = []
    for mapping in field_domain.mapped_fields(mappings):
        mapped_preview.append(
            {
                "external_field_id": mapping["external_field_id"],
                "external_field_name": mapping["external_field_name"],
                "raptor_field": mapping.get("raptor_field") or "",
                "preview": field_domain.mapped_preview(mapping, sample_values or {}),
                "type": mapping.get("external_field_type") or "string",
            }
        )
    ask = []
    for mapping in field_domain.ask_fields(mappings):
        ask.append(
            {
                "external_field_id": mapping["external_field_id"],
                "external_field_name": mapping["external_field_name"],
                "type": mapping.get("external_field_type") or "string",
                "required": bool(mapping.get("required")),
                "allowed_values": mapping.get("allowed_values") or [],
                "static_value": mapping.get("static_value") or "",
            }
        )
    return {
        "connection": _public_connection(connection),
        "template": _public_template(template),
        "findings": items,
        "mapped": mapped_preview,
        "ask": ask,
        "refresh_warning": refresh_error or "",
    }, 200


def export_findings(data: Dict[str, Any], username: str) -> Tuple[Dict[str, Any], int]:
    template, connection, error = _resolve_template(data)
    if error:
        return error
    finding_ids = _finding_ids_from_request(data)
    if not finding_ids:
        return {"error": "Select at least one finding."}, 400
    extras = (data or {}).get("extras") if isinstance((data or {}).get("extras"), dict) else {}
    mappings = integrations_repository.list_mappings(int(template["id"]))
    mappings, _warning = _refresh_allowed_values(connection, template, mappings)
    wave_id = (data or {}).get("wave_id")
    scope = "wave" if wave_id not in (None, "", 0) else "finding"
    results = []
    created = 0
    failed = 0
    try:
        client = _client_for(connection)
    except ValueError as exc:
        return {"error": str(exc)}, 400
    try:
        dojo_test_id = None
        dojo_user_id = None
        if connection["kind"] == "defectdojo":
            try:
                dojo_test_id, dojo_user_id = _resolve_dojo_targets(client, template, data)
            except DefectDojoError as exc:
                return {"error": str(exc)}, 400
        for finding_id in finding_ids:
            context = _load_finding_context(finding_id)
            if not context:
                results.append({"id": finding_id, "status": "failed", "error": "Finding not found."})
                failed += 1
                continue
            values = field_domain.raptor_values(context)
            application_id = context["finding"].get("application_id")
            used_wave = wave_id or (context.get("wave") or {}).get("id")
            existing = _latest_export(str(context["finding"]["id"]), connection["kind"])
            if _already_at_destination(connection["kind"], context["finding"], existing):
                results.append(
                    {
                        "id": context["finding"]["id"],
                        "title": values["title"],
                        "status": "skipped",
                        "error": "Already reported.",
                        "external_url": _http_ticket_url(context["finding"])
                        or (existing or {}).get("external_url")
                        or "",
                        "external_id": (existing or {}).get("external_id") or "",
                    }
                )
                continue
            if connection["kind"] == "jira":
                item = _export_jira(
                    client,
                    connection,
                    template,
                    mappings,
                    values,
                    extras,
                    context,
                    username,
                    scope,
                    used_wave,
                    application_id,
                )
            else:
                item = _export_dojo(
                    client,
                    connection,
                    template,
                    mappings,
                    values,
                    extras,
                    context,
                    username,
                    scope,
                    used_wave,
                    application_id,
                    dojo_test_id,
                    dojo_user_id,
                )
            results.append(item)
            if item.get("status") == "created":
                created += 1
            else:
                failed += 1
    finally:
        try:
            client.close()
        except Exception:
            pass
    return {"results": results, "created": created, "failed": failed}, 200 if failed == 0 else 207


def list_finding_exports(finding_id: str) -> Tuple[Dict[str, Any], int]:
    if not pentest_findings_repository.get_finding(finding_id):
        return {"error": "Finding not found."}, 404
    return {"exports": integrations_repository.list_exports_for_findings([finding_id])}, 200


def _resolve_template(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Tuple[Dict[str, Any], int]]]:
    template_id = (data or {}).get("template_id")
    if template_id in (None, ""):
        kind = _normalize_kind((data or {}).get("kind"))
        ready, _status = list_ready(kind)
        connections = ready.get("connections") or []
        chosen = None
        for connection in connections:
            for template in connection.get("templates") or []:
                if template.get("is_default"):
                    chosen = template
                    break
            if chosen:
                break
        if not chosen and connections and connections[0].get("templates"):
            chosen = connections[0]["templates"][0]
        if not chosen:
            return None, None, ({"error": "No ticket template is configured."}, 400)
        template_id = chosen["id"]
    template = integrations_repository.get_template(int(template_id))
    if not template:
        return None, None, ({"error": "Template not found."}, 404)
    connection = integrations_repository.get_connection(int(template["connection_id"]))
    if not connection:
        return None, None, ({"error": "Integration not found."}, 404)
    return template, connection, None


def _finding_ids_from_request(data: Dict[str, Any]) -> List[str]:
    raw = (data or {}).get("finding_ids")
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw if item not in (None, "")]
    if (data or {}).get("finding_id") not in (None, ""):
        return [str(data["finding_id"])]
    wave_id = (data or {}).get("wave_id")
    app_id = (data or {}).get("application_id") or (data or {}).get("app_id")
    if wave_id not in (None, "") and app_id not in (None, ""):
        payload, status = phase2b_service.get_wave(int(app_id), int(wave_id))
        if status == 200:
            return [str(item.get("id")) for item in payload.get("findings") or [] if item.get("id")]
    return []


def _refresh_allowed_values(
    connection: Dict[str, Any],
    template: Dict[str, Any],
    mappings: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], str]:
    if connection["kind"] != "jira":
        return mappings, ""
    try:
        client = _client_for(connection)
        live = field_domain.parse_jira_fields(
            client.get_create_fields(template["external_project_key"], template["issue_type_id"])
        )
        client.close()
    except (JiraError, ValueError) as exc:
        return mappings, str(exc)
    merged = field_domain.merge_mappings(live, mappings, "jira")
    integrations_repository.replace_mappings(int(template["id"]), merged)
    return merged, ""


def _read_pentest_image(filename: str) -> Optional[Tuple[bytes, str]]:
    from app.integrations.storage.offsec_storage import fetch_image, guess_image_mimetype

    try:
        blob = fetch_image(filename)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read pentest image %s for export: %s", filename, exc)
        return None
    raw = blob.getvalue() if hasattr(blob, "getvalue") else blob.read()
    if not raw:
        return None
    ext = str(filename).rsplit(".", 1)[-1].lower()
    return raw, guess_image_mimetype(ext)


def _screenshot_files(values: Dict[str, Any]) -> List[tuple]:
    files = []
    for filename in field_domain.narrative_image_filenames(values):
        loaded = _read_pentest_image(filename)
        if not loaded:
            continue
        raw, content_type = loaded
        files.append((filename, raw, content_type))
    return files


def _attach_jira_screenshots(client: JiraClient, issue_key: str, values: Dict[str, Any]) -> None:
    files = _screenshot_files(values)
    if not files:
        return
    try:
        client.add_attachments(issue_key, files)
    except JiraError as exc:
        logger.warning("Jira accepted the issue but not the screenshots (%s): %s", issue_key, exc)


def _attach_dojo_screenshots(client: DefectDojoClient, finding_id: str, values: Dict[str, Any]) -> None:
    files = _screenshot_files(values)
    if not files:
        return
    try:
        client.add_files(finding_id, files)
    except DefectDojoError as exc:
        logger.warning("DefectDojo accepted the finding but not the screenshots (%s): %s", finding_id, exc)


def _export_jira(
    client: JiraClient,
    connection: Dict[str, Any],
    template: Dict[str, Any],
    mappings: List[Dict[str, Any]],
    values: Dict[str, Any],
    extras: Dict[str, Any],
    context: Dict[str, Any],
    username: str,
    scope: str,
    wave_id: Any,
    application_id: Any,
) -> Dict[str, Any]:
    finding_id = context["finding"]["id"]
    fields, errors = field_domain.build_jira_issue_fields(
        mappings,
        values,
        extras,
        template["external_project_key"],
        template["issue_type_id"],
        adf=str((connection.get("extra") or {}).get("api_style") or client.api_style) != "2",
    )
    if errors:
        export = integrations_repository.insert_export(
            {
                "connection_id": connection["id"],
                "template_id": template["id"],
                "kind": "jira",
                "scope": scope,
                "finding_id": finding_id,
                "wave_id": wave_id,
                "application_id": application_id,
                "status": "failed",
                "error": "; ".join(errors),
                "created_by": username,
            }
        )
        return {**export, "id": finding_id, "title": values["title"]}
    try:
        created = client.create_issue(fields)
        pentest_findings_repository.update_finding_fields(finding_id, {"ticket_url": created["url"]})
        _attach_jira_screenshots(client, created["key"], values)
        export = integrations_repository.insert_export(
            {
                "connection_id": connection["id"],
                "template_id": template["id"],
                "kind": "jira",
                "scope": scope,
                "finding_id": finding_id,
                "wave_id": wave_id,
                "application_id": application_id,
                "external_id": created["key"],
                "external_url": created["url"],
                "payload": {"fields": {key: fields[key] for key in fields if key not in {"description"}}},
                "status": "created",
                "created_by": username,
            }
        )
        return {**export, "id": finding_id, "title": values["title"], "external_url": created["url"], "external_id": created["key"]}
    except JiraError as exc:
        export = integrations_repository.insert_export(
            {
                "connection_id": connection["id"],
                "template_id": template["id"],
                "kind": "jira",
                "scope": scope,
                "finding_id": finding_id,
                "wave_id": wave_id,
                "application_id": application_id,
                "status": "failed",
                "error": str(exc),
                "created_by": username,
            }
        )
        return {**export, "id": finding_id, "title": values["title"]}


def _resolve_dojo_targets(client: DefectDojoClient, template: Dict[str, Any], data: Dict[str, Any]) -> Tuple[int, Optional[int]]:
    extra = dict(template.get("extra") or {})
    product_id = str(extra.get("product_id") or template.get("external_project_key") or "")
    engagement_mode = str(extra.get("engagement_mode") or "per_wave")
    engagement_id = str(extra.get("engagement_id") or "")
    if engagement_mode == "ask":
        engagement_id = str((data or {}).get("engagement_id") or engagement_id)
    elif engagement_mode == "per_wave":
        wave_name = str((data or {}).get("wave_name") or "").strip()
        if not wave_name and (data or {}).get("wave_id") not in (None, "") and (data or {}).get("application_id") not in (None, ""):
            payload, status = phase2b_service.get_wave(int(data["application_id"]), int(data["wave_id"]))
            if status == 200:
                wave_name = str((payload.get("wave") or {}).get("name") or "")
        wave_name = wave_name or "RAPTOR"
        engagement = client.find_or_create_engagement(product_id, wave_name)
        engagement_id = engagement["id"]
    if not engagement_id:
        raise DefectDojoError("Select or configure a DefectDojo engagement.")
    test_mode = str(extra.get("test_mode") or "create")
    test_id = str(extra.get("test_id") or "")
    if test_mode == "ask":
        test_id = str((data or {}).get("test_id") or test_id)
    elif test_mode == "create" or not test_id:
        test = client.find_or_create_test(engagement_id, str(extra.get("test_title") or "RAPTOR"))
        test_id = test["id"]
    if not test_id:
        raise DefectDojoError("Select or configure a DefectDojo test.")
    user_id = None
    try:
        me = client.myself()
        if me.get("id") is not None:
            user_id = int(me["id"])
    except Exception:
        user_id = None
    return int(test_id), user_id


def _export_dojo(
    client: DefectDojoClient,
    connection: Dict[str, Any],
    template: Dict[str, Any],
    mappings: List[Dict[str, Any]],
    values: Dict[str, Any],
    extras: Dict[str, Any],
    context: Dict[str, Any],
    username: str,
    scope: str,
    wave_id: Any,
    application_id: Any,
    test_id: int,
    user_id: Optional[int],
) -> Dict[str, Any]:
    finding_id = context["finding"]["id"]
    payload, errors = field_domain.build_defectdojo_finding(mappings, values, extras)
    payload["test"] = test_id
    payload.setdefault("active", True)
    payload.setdefault("verified", True)
    payload.setdefault("false_p", False)
    payload.setdefault("duplicate", False)
    if payload.get("severity") and not payload.get("numerical_severity"):
        payload["numerical_severity"] = field_domain.dojo_numerical_severity(payload["severity"])
    if user_id is not None:
        payload.setdefault("found_by", [user_id])
    if errors:
        export = integrations_repository.insert_export(
            {
                "connection_id": connection["id"],
                "template_id": template["id"],
                "kind": "defectdojo",
                "scope": scope,
                "finding_id": finding_id,
                "wave_id": wave_id,
                "application_id": application_id,
                "status": "failed",
                "error": "; ".join(errors),
                "created_by": username,
            }
        )
        return {**export, "id": finding_id, "title": values["title"]}
    try:
        created = client.create_finding(payload)
        _attach_dojo_screenshots(client, created["id"], values)
        export = integrations_repository.insert_export(
            {
                "connection_id": connection["id"],
                "template_id": template["id"],
                "kind": "defectdojo",
                "scope": scope,
                "finding_id": finding_id,
                "wave_id": wave_id,
                "application_id": application_id,
                "external_id": created["id"],
                "external_url": created["url"],
                "payload": {key: payload[key] for key in payload if key != "description"},
                "status": "created",
                "created_by": username,
            }
        )
        return {**export, "id": finding_id, "title": values["title"], "external_url": created["url"], "external_id": created["id"]}
    except DefectDojoError as exc:
        export = integrations_repository.insert_export(
            {
                "connection_id": connection["id"],
                "template_id": template["id"],
                "kind": "defectdojo",
                "scope": scope,
                "finding_id": finding_id,
                "wave_id": wave_id,
                "application_id": application_id,
                "status": "failed",
                "error": str(exc),
                "created_by": username,
            }
        )
        return {**export, "id": finding_id, "title": values["title"]}
