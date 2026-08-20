import json
import logging
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from flask import jsonify, send_file

from app.config import DB_PATH
from app.domain.offsec.shared import safe_json_load
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.integrations.reporting.report_context_builder import (
    build_sheet_context,
    export_cap_error,
    sheet_content_hash,
)
from app.integrations.reporting.report_pdf_render import render_pentest_report_pdf
from app.integrations.storage.offsec_storage import fetch_image, ftp_connect, save_report
from app.repositories import applications_repository, environments_repository, pentest_findings_repository
from app.services.offsec.offsec_generated_reports import load_enabled_checklist_templates
from app.services.offsec.offsec_templates import bind_report_template_logo_for_template
from app.services.report_brand_kit_service import apply_brand_kit, fetch_brand_kit
from app.services.phase2b_service import package_defaults, sign_export, visible_env_ids

logger = logging.getLogger(__name__)


def _enabled_template(cursor, template_id: Any):
    if template_id is not None:
        cursor.execute(
            """
            SELECT id, key, name, description, template_json, enabled
            FROM report_templates
            WHERE id = ?
            """,
            (int(template_id),),
        )
        row = cursor.fetchone()
        if row and int(row["enabled"] or 0) == 1:
            return row
        return None
    cursor.execute(
        """
        SELECT id, key, name, description, template_json, enabled
        FROM report_templates
        WHERE enabled = 1
        ORDER BY LOWER(name) ASC
        LIMIT 1
        """
    )
    return cursor.fetchone()


def _default_env_ids(application_id: int, requested: Any) -> Tuple[List[int], List[Dict[str, Any]]]:
    envs = environments_repository.fetch_environments(application_id)
    if isinstance(requested, list) and requested:
        wanted = {int(item) for item in requested}
        selected = [env for env in envs if int(env["id"]) in wanted and env.get("slug") != "unassigned"]
        return [int(env["id"]) for env in selected], envs
    selected = [
        env
        for env in envs
        if env.get("slug") == "prod" or (env.get("is_production") and env.get("include_in_exec_report"))
    ]
    if not selected:
        selected = [env for env in envs if env.get("include_in_exec_report")]
    return [int(env["id"]) for env in selected], envs


def _pack_findings(
    application_id: int,
    selected_env_ids: List[int],
    include_drafts: bool,
    severity_floor: float = 0.0,
    host_prefix: str = "",
    host_suffix: str = "",
    occurrence_statuses: Optional[List[str]] = None,
    wave_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], int, List[Dict[str, Any]], int]:
    findings, total = pentest_findings_repository.fetch_app_findings(
        application_id,
        include_drafts=True,
        env_ids=selected_env_ids or None,
        wave_id=wave_id,
        limit=200,
        offset=0,
    )
    packed = []
    excluded_drafts = 0
    unassigned_hosts = []
    seen_unassigned = set()
    prefix = str(host_prefix or "").strip().lower()
    suffix = str(host_suffix or "").strip().lower()
    floor = float(severity_floor or 0)

    def _name_ok(name: str) -> bool:
        value = str(name or "").lower()
        if prefix and not value.startswith(prefix):
            return False
        if suffix and not value.endswith(suffix):
            return False
        return True

    for finding in findings:
        if finding.get("status") == "draft":
            excluded_drafts += 1
            if not include_drafts:
                continue
        if float(finding.get("baseScore") or 0) < floor:
            continue
        for occ in finding.get("occurrences") or []:
            if str(occ.get("environment_slug") or "") == "unassigned":
                key = int(occ.get("record_id") or 0)
                if key and key not in seen_unassigned:
                    seen_unassigned.add(key)
                    unassigned_hosts.append({"record_id": key, "name": occ.get("dns_name")})
        packed_occ = _split_occurrences(finding.get("occurrences") or [], selected_env_ids)
        packed_occ["primary"] = [item for item in packed_occ["primary"] if _name_ok(item.get("dns_name") or "")]
        packed_occ["observed"] = [item for item in packed_occ["observed"] if _name_ok(item.get("dns_name") or "")]
        if occurrence_statuses:
            allowed_statuses = {str(item) for item in occurrence_statuses}
            packed_occ["primary"] = [
                item for item in packed_occ["primary"] if str(item.get("status") or "") in allowed_statuses
            ]
            packed_occ["observed"] = [
                item for item in packed_occ["observed"] if str(item.get("status") or "") in allowed_statuses
            ]
        if not packed_occ["primary"]:
            continue
        item = dict(finding)
        item["occurrences"] = packed_occ["primary"]
        item["also_observed"] = packed_occ["observed"]
        packed.append(item)
    return packed, excluded_drafts, unassigned_hosts, int(total or 0)


def _split_occurrences(occurrences: List[Dict[str, Any]], selected_env_ids: List[int]) -> Dict[str, List[Dict[str, Any]]]:
    selected = set(int(item) for item in selected_env_ids)
    if not occurrences:
        return {"primary": [], "observed": []}
    record_ids = [int(item.get("record_id")) for item in occurrences if item.get("record_id") is not None]
    env_by_record: Dict[int, Any] = {}
    slug_by_record: Dict[int, Dict[str, Any]] = {}
    if record_ids:
        placeholders = ",".join("?" for _ in record_ids)
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute(
                f"""
                SELECT r.id, r.environment_id, e.slug, e.is_production
                FROM records r
                LEFT JOIN environments e ON e.id = r.environment_id
                WHERE r.id IN ({placeholders})
                """,
                tuple(record_ids),
            )
            for row in c.fetchall() or []:
                env_by_record[int(row["id"])] = row.get("environment_id")
                slug_by_record[int(row["id"])] = {
                    "slug": row.get("slug"),
                    "is_production": bool(row.get("is_production")),
                }
    primary = []
    for occ in occurrences:
        if occ.get("record_id") is None:
            continue
        record_id = int(occ["record_id"])
        meta = slug_by_record.get(record_id) or {}
        env_id = env_by_record.get(record_id)
        if meta.get("slug") == "unassigned":
            continue
        if env_id in selected:
            primary.append(occ)
    if not primary:
        return {"primary": [], "observed": []}
    extras = []
    for occ in occurrences:
        if occ in primary or occ.get("record_id") is None:
            continue
        meta = slug_by_record.get(int(occ["record_id"])) or {}
        if meta.get("slug") == "unassigned":
            continue
        extras.append(occ)
    return {"primary": primary, "observed": extras}


def generate_scoped_report(
    *,
    scope_kind: str,
    scope_id: int,
    data: Dict[str, Any],
    username: str,
    application_id: Optional[int] = None,
    role: str = "",
) -> Tuple[Dict[str, Any], int]:
    payload = data or {}
    if scope_kind == "application":
        application_id = scope_id
    elif scope_kind == "environment":
        if not application_id:
            return {"error": "application_id is required for environment export."}, 400
    else:
        return {"error": "Unsupported scope."}, 400

    app = applications_repository.fetch_application(application_id)
    if not app:
        return {"error": "Application not found."}, 404

    package_info = package_defaults(payload.get("package"))
    package_key = package_info["package"]
    wave_id = payload.get("wave_id")
    parsed_wave_id = None
    wave_row = None
    requested_envs = payload.get("selected_env_ids")
    if package_key == "wave_archive":
        if wave_id in (None, "", "null"):
            return {"error": "wave_id is required for wave_archive."}, 400
        try:
            parsed_wave_id = int(wave_id)
        except (TypeError, ValueError):
            return {"error": "Invalid wave_id."}, 400
        from app.repositories.phase2b_repository import get_wave

        wave_row = get_wave(parsed_wave_id)
        if not wave_row or int(wave_row.get("application_id") or 0) != int(application_id):
            return {"error": "Wave not found."}, 404
        if not (isinstance(requested_envs, list) and requested_envs):
            requested_envs = wave_row.get("env_ids") or []

    if package_key != "owner_delivery" and isinstance(requested_envs, list):
        if requested_envs:
            selected_env_ids, all_envs = _default_env_ids(application_id, requested_envs)
        else:
            all_envs = environments_repository.fetch_environments(application_id)
            selected_env_ids = [
                int(env["id"]) for env in all_envs if env.get("slug") != "unassigned"
            ]
    else:
        selected_env_ids, all_envs = _default_env_ids(application_id, requested_envs)
    if scope_kind == "environment":
        selected_env_ids = [scope_id]
    if not selected_env_ids:
        return {"error": "No environments selected."}, 400

    allowed = visible_env_ids(application_id, username, role)
    if allowed is not None:
        allowed_set = {int(item) for item in allowed}
        if any(int(env_id) not in allowed_set for env_id in selected_env_ids):
            return {"error": "One or more environments are not visible to this user."}, 403

    if "include_drafts" in payload:
        include_drafts = bool(payload.get("include_drafts"))
    else:
        include_drafts = bool(package_info["include_drafts"])
    try:
        severity_floor = float(payload.get("severity_floor") or 0)
    except (TypeError, ValueError):
        severity_floor = 0.0
    findings, excluded_drafts, unassigned_hosts, packed_total = _pack_findings(
        application_id,
        selected_env_ids,
        include_drafts,
        severity_floor=severity_floor,
        host_prefix=str(payload.get("host_prefix") or ""),
        host_suffix=str(payload.get("host_suffix") or ""),
        occurrence_statuses=package_info.get("occurrence_statuses"),
        wave_id=parsed_wave_id,
    )
    cap_error = export_cap_error(packed_total)
    if cap_error:
        return cap_error

    selected_envs = [env for env in all_envs if int(env["id"]) in set(selected_env_ids)]
    watermark = (
        "PRODUCTION"
        if selected_envs and all(env.get("is_production") or env.get("slug") == "prod" for env in selected_envs)
        else "NON-PROD"
    )

    preview_payload = {
        "preview": True,
        "finding_count": len(findings),
        "excluded_draft_count": excluded_drafts,
        "selected_env_ids": selected_env_ids,
        "watermark": watermark,
        "unassigned_in_scope_hosts": unassigned_hosts,
        "package": package_key,
        "wave_id": parsed_wave_id,
        "include_drafts": include_drafts,
        "findings": [
            {
                "id": item.get("id"),
                "title": item.get("title") or item.get("categoryName"),
                "status": item.get("status"),
                "baseScore": item.get("baseScore"),
                "also_observed": item.get("also_observed") or [],
            }
            for item in findings
        ],
    }
    if payload.get("preview"):
        return preview_payload, 200

    try:
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            template_row = _enabled_template(c, payload.get("template_id"))
            if not template_row:
                return {"error": "No enabled report template available."}, 404
            template_definition = safe_json_load(template_row["template_json"], {})
            if not isinstance(template_definition, dict):
                return {"error": "Report template definition is invalid."}, 500
            template_definition, logo_error = bind_report_template_logo_for_template(
                c, template_row["id"], template_definition
            )
            if logo_error:
                return {"error": logo_error}, 400
            template_definition = apply_brand_kit(template_definition, fetch_brand_kit(c))

            content_hash = sheet_content_hash(findings, selected_env_ids)
            signature = sign_export(content_hash)
            report_context = build_sheet_context(
                scope=scope_kind,
                package=package_key,
                app=app,
                selected_envs=selected_envs,
                packed_findings=findings,
                username=username,
                watermark=watermark,
                wave=wave_row,
                content_hash=content_hash,
                signature=signature,
            )
            pdf_content = render_pentest_report_pdf(
                report_context,
                template_definition,
                checklist_templates=load_enabled_checklist_templates(),
                image_fetcher=fetch_image,
                generated_by=username,
            )
            file_path = save_report(f"{scope_kind}-{scope_id}", pdf_content)
            finding_ids = [str(item.get("id")) for item in findings]
            c.execute(
                """
                INSERT INTO report_exports (
                    scope_kind, scope_id, template_id, generated_by, file_path,
                    source_finding_ids, excluded_draft_count, selected_env_ids,
                    content_hash, package, signature, wave_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    scope_kind,
                    scope_id,
                    template_row["id"],
                    username,
                    file_path,
                    json.dumps(finding_ids),
                    excluded_drafts,
                    json.dumps(selected_env_ids),
                    content_hash,
                    package_key,
                    signature,
                    parsed_wave_id,
                ),
            )
            inserted = c.fetchone()
            export_id = inserted["id"] if isinstance(inserted, dict) else inserted[0]
            conn.commit()
        return {
            "export_id": export_id,
            "file_path": file_path,
            "finding_count": len(findings),
            "excluded_draft_count": excluded_drafts,
            "selected_env_ids": selected_env_ids,
            "watermark": watermark,
            "unassigned_in_scope_hosts": unassigned_hosts,
            "package": package_key,
            "signature": signature,
            "wave_id": parsed_wave_id,
        }, 200
    except Exception as exc:
        logger.error("Failed to generate scoped report: %s", exc)
        return {"error": "Failed to generate report."}, 500


def download_export(export_id: int):
    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM report_exports WHERE id = ?", (export_id,))
        row = c.fetchone()
    if not row or not row.get("file_path"):
        return jsonify({"error": "Export not found."}), 404
    try:
        ftp = ftp_connect()
        file_data = BytesIO()
        ftp.retrbinary(f"RETR {row['file_path']}", file_data.write)
        ftp.quit()
        file_data.seek(0)
        return send_file(
            file_data,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"raptor_{row['scope_kind']}_{row['scope_id']}_{export_id}.pdf",
        )
    except Exception as exc:
        logger.error("Failed to download export %s: %s", export_id, exc)
        return jsonify({"error": "Failed to retrieve export."}), 500


def record_host_export(
    record_id: int,
    file_path: str,
    template_id: Any,
    username: str,
    content_hash: str = "",
    signature: str = "",
) -> None:
    try:
        with get_db_connection(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO report_exports (
                    scope_kind, scope_id, template_id, generated_by, file_path,
                    package, content_hash, signature
                )
                VALUES ('host', ?, ?, ?, ?, 'host', ?, ?)
                """,
                (record_id, template_id, username, file_path, content_hash, signature),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not persist host report_exports row: %s", exc)
