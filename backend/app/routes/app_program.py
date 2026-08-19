from flask import Blueprint, jsonify, request, session

from app.http.request_utils import parse_json_object
from app.http.decorators.admin_required import admin_or_manager_required
from app.http.decorators.permission_required import permission_required
from app.services import app_program_service, app_report_service, phase2b_service

app_program_bp = Blueprint("app_program", __name__)


@app_program_bp.route("/api/apps/<int:app_id>", methods=["GET"])
@permission_required("view_security_dashboard")
def get_app(app_id: int):
    payload, status_code = app_program_service.get_app(
        app_id, username=session.get("username") or "", role=session.get("user_type") or ""
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments", methods=["GET"])
@permission_required("view_records")
def list_environments(app_id: int):
    payload, status_code = app_program_service.list_environments(
        app_id, username=session.get("username") or "", role=session.get("user_type") or ""
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments", methods=["POST"])
@permission_required("manage_apps")
def create_environment(app_id: int):
    payload, status_code = app_program_service.create_environment(app_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments/<int:env_id>", methods=["PUT"])
@permission_required("manage_apps")
def update_environment(app_id: int, env_id: int):
    payload, status_code = app_program_service.update_environment(app_id, env_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments/<int:env_id>", methods=["DELETE"])
@permission_required("manage_apps")
def delete_environment(app_id: int, env_id: int):
    payload, status_code = app_program_service.delete_environment(app_id, env_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/hosts/assign", methods=["POST"])
@permission_required("manage_apps")
def assign_hosts(app_id: int):
    payload, status_code = app_program_service.assign_hosts(app_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/hosts/assign-tester", methods=["POST"])
@permission_required("modify_pentests")
def assign_host_testers(app_id: int):
    payload, status_code = app_program_service.assign_host_testers(app_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/hosts/search", methods=["GET"])
@permission_required("view_security_dashboard")
def search_hosts():
    payload, status_code = app_program_service.search_hosts(request.args)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/hosts", methods=["GET"])
@permission_required("view_security_dashboard")
def list_hosts(app_id: int):
    payload, status_code = app_program_service.list_hosts(
        app_id,
        request.args,
        username=session.get("username") or "",
        role=session.get("user_type") or "",
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/findings", methods=["GET"])
@permission_required("view_pentest_page")
def list_findings(app_id: int):
    payload, status_code = app_program_service.list_findings(
        app_id,
        request.args,
        username=session.get("username") or "",
        role=session.get("user_type") or "",
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/findings", methods=["POST"])
@permission_required("modify_pentests")
def create_finding(app_id: int):
    payload, status_code = app_program_service.create_finding(
        app_id, parse_json_object(), session.get("username", "unknown")
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/findings/<finding_id>", methods=["GET"])
@permission_required("view_pentest_page")
def get_finding(finding_id: str):
    payload, status_code = app_program_service.get_finding(finding_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/findings/<finding_id>", methods=["PATCH"])
@permission_required("modify_pentests")
def patch_finding(finding_id: str):
    payload, status_code = app_program_service.patch_finding(finding_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/findings/<finding_id>/occurrences", methods=["POST"])
@permission_required("modify_pentests")
def add_occurrences(finding_id: str):
    payload, status_code = app_program_service.add_occurrences(finding_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/findings/<finding_id>/occurrences/<int:record_id>", methods=["PATCH"])
@permission_required("modify_pentests")
def patch_occurrence(finding_id: str, record_id: int):
    payload, status_code = app_program_service.patch_occurrence(
        finding_id, record_id, parse_json_object()
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/occurrences/bulk-status", methods=["POST"])
@permission_required("modify_pentests")
def bulk_set_occurrence_status(app_id: int):
    payload, status_code = app_program_service.bulk_set_occurrence_status(app_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/findings/<finding_id>/merge", methods=["POST"])
@permission_required("modify_pentests")
def merge_findings(finding_id: str):
    payload, status_code = app_program_service.merge_findings(finding_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/findings/<finding_id>/promote", methods=["POST"])
@permission_required("modify_pentests")
def promote_finding(finding_id: str):
    payload, status_code = app_program_service.promote_finding(finding_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/generate-report", methods=["POST"])
@permission_required("export_pentests")
def generate_app_report(app_id: int):
    payload, status_code = app_report_service.generate_scoped_report(
        scope_kind="application",
        scope_id=app_id,
        data=parse_json_object(),
        username=session.get("username", "unknown"),
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments/<int:env_id>/generate-report", methods=["POST"])
@permission_required("export_pentests")
def generate_env_report(app_id: int, env_id: int):
    payload, status_code = app_report_service.generate_scoped_report(
        scope_kind="environment",
        scope_id=env_id,
        data=parse_json_object(),
        username=session.get("username", "unknown"),
        application_id=app_id,
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/report-exports/<int:export_id>", methods=["GET"])
@permission_required("export_pentests")
def download_report_export(export_id: int):
    return app_report_service.download_export(export_id)


@app_program_bp.route("/api/report-exports/<int:export_id>/verify", methods=["GET"])
@permission_required("export_pentests")
def verify_report_export(export_id: int):
    payload, status_code = phase2b_service.verify_export(export_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves", methods=["GET"])
@permission_required("view_pentest_page")
def list_waves(app_id: int):
    payload, status_code = phase2b_service.list_waves(app_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>", methods=["GET"])
@permission_required("view_pentest_page")
def get_wave(app_id: int, wave_id: int):
    payload, status_code = phase2b_service.get_wave(app_id, wave_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves", methods=["POST"])
@permission_required("modify_pentests")
def create_wave(app_id: int):
    payload, status_code = phase2b_service.create_wave(
        app_id, parse_json_object(), session.get("username", "unknown")
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/members", methods=["PUT"])
@permission_required("modify_pentests")
def put_wave_members(app_id: int, wave_id: int):
    payload, status_code = phase2b_service.put_wave_members(app_id, wave_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/hosts/claim", methods=["POST"])
@permission_required("modify_pentests")
def claim_wave_hosts(app_id: int, wave_id: int):
    payload, status_code = phase2b_service.claim_wave_hosts(
        app_id, wave_id, parse_json_object(), session.get("username") or ""
    )
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/environments", methods=["PUT"])
@permission_required("modify_pentests")
def put_wave_environments(app_id: int, wave_id: int):
    payload, status_code = phase2b_service.put_wave_environments(app_id, wave_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/hosts/scope", methods=["POST"])
@permission_required("modify_pentests")
def set_wave_host_scope(app_id: int, wave_id: int):
    payload, status_code = phase2b_service.set_wave_host_scope(app_id, wave_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/start", methods=["POST"])
@permission_required("modify_pentests")
def start_wave(app_id: int, wave_id: int):
    payload, status_code = phase2b_service.start_wave(app_id, wave_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/close", methods=["POST"])
@permission_required("modify_pentests")
def close_wave(app_id: int, wave_id: int):
    payload, status_code = phase2b_service.close_wave(app_id, wave_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>", methods=["DELETE"])
@admin_or_manager_required
def delete_wave(app_id: int, wave_id: int):
    payload, status_code = phase2b_service.delete_wave(app_id, wave_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments/<int:env_id>/acl", methods=["GET"])
@permission_required("view_pentest_page")
def get_acl(app_id: int, env_id: int):
    payload, status_code = phase2b_service.get_acl(app_id, env_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments/<int:env_id>/acl", methods=["PUT"])
@permission_required("manage_apps")
def put_acl(app_id: int, env_id: int):
    payload, status_code = phase2b_service.put_acl(app_id, env_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments/<int:env_id>/checklists", methods=["GET"])
@permission_required("view_pentest_page")
def get_env_checklists(app_id: int, env_id: int):
    payload, status_code = phase2b_service.get_env_checklists(app_id, env_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/environments/<int:env_id>/checklists", methods=["PUT"])
@permission_required("manage_apps")
def put_env_checklists(app_id: int, env_id: int):
    payload, status_code = phase2b_service.put_env_checklists(app_id, env_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/dns-zones", methods=["GET"])
@permission_required("view_pentest_page")
def list_zones():
    app_id = request.args.get("application_id")
    parsed = None
    if app_id not in (None, "", "null"):
        try:
            parsed = int(app_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid application_id."}), 400
    payload, status_code = phase2b_service.list_zones(parsed)
    return jsonify(payload), status_code


@app_program_bp.route("/api/dns-zones", methods=["POST"])
@permission_required("manage_apps")
def create_zone():
    payload, status_code = phase2b_service.create_zone(parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/dns-zones/<int:zone_id>", methods=["DELETE"])
@permission_required("manage_apps")
def delete_zone(zone_id: int):
    payload, status_code = phase2b_service.delete_zone(zone_id)
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/hosts/<int:record_id>/share", methods=["POST"])
@permission_required("manage_apps")
def share_host(app_id: int, record_id: int):
    payload, status_code = phase2b_service.share_host(app_id, record_id, parse_json_object())
    return jsonify(payload), status_code


@app_program_bp.route("/api/apps/<int:app_id>/shared-hosts", methods=["GET"])
@permission_required("view_pentest_page")
def list_shared_hosts(app_id: int):
    payload, status_code = phase2b_service.list_shared(app_id)
    return jsonify(payload), status_code
