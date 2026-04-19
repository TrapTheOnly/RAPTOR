from flask import Blueprint, jsonify, request, session

from app.http.decorators.admin_required import admin_required
from app.http.decorators.login_required import login_required_json
from app.http.decorators.service_api_key_required import service_api_key_required
from app.services.scanner_service import (
    get_scanner_config_payload,
    launch_scan_payload,
    update_scanner_config_payload,
)

scanner_bp = Blueprint("scanner", __name__)


@scanner_bp.route("/admin/scanner-config", methods=["GET"])
@login_required_json
@admin_required
def get_scanner_config_route():
    payload, status_code = get_scanner_config_payload()
    return jsonify(payload), status_code


@scanner_bp.route("/admin/scanner-config", methods=["PUT"])
@login_required_json
@admin_required
def update_scanner_config_route():
    body = request.get_json(silent=True) or {}
    actor = session.get("username", "admin")
    payload, status_code = update_scanner_config_payload(body, actor)
    return jsonify(payload), status_code


@scanner_bp.route("/service-api/v1/pentests/<int:record_id>/launch-scan", methods=["POST"])
@service_api_key_required("pentests.write")
def launch_scan_route(record_id):
    payload, status_code = launch_scan_payload(record_id)
    return jsonify(payload), status_code


@scanner_bp.route("/pentest/<int:record_id>/launch-scan", methods=["POST"])
@login_required_json
def launch_scan_ui_route(record_id):
    from app.repositories.offsec.offsec_records import get_pentest_access_role
    access_role = get_pentest_access_role(record_id)
    if access_role not in {"owner", "manager_override", "admin_override"}:
        return jsonify({"error": "You do not have permission to launch a scan for this record."}), 403
    payload, status_code = launch_scan_payload(record_id)
    return jsonify(payload), status_code


__all__ = ["scanner_bp"]
