import json
import time

from flask import Blueprint, Response, jsonify, request, session

from app.http.decorators.admin_required import admin_required
from app.http.decorators.login_required import login_required_json
from app.http.decorators.permission_required import permission_required
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


@scanner_bp.route("/pentest/<int:record_id>/reset-scan", methods=["POST"])
@login_required_json
def reset_scan_ui_route(record_id):
    from app.repositories.offsec.offsec_records import get_pentest_access_role
    from app.services.service_api_service import reset_scan_payload
    access_role = get_pentest_access_role(record_id)
    if access_role not in {"owner", "manager_override", "admin_override"}:
        return jsonify({"error": "You do not have permission to reset this scan."}), 403
    payload, status_code = reset_scan_payload(record_id)
    return jsonify(payload), status_code


@scanner_bp.route("/pentest/<int:record_id>/scan-events/stream", methods=["GET"])
@permission_required("view_pentest_page")
def scan_events_stream(record_id):
    from app.repositories.offsec.offsec_records import enforce_pentest_record_access
    from app.repositories.scan_events_repository import fetch_scan_events_after

    allowed, error = enforce_pentest_record_access(record_id, "access")
    if not allowed:
        return jsonify({"error": error or "Access denied."}), 403

    after_id = int(request.args.get("after", 0))

    def event_stream():
        nonlocal after_id
        idle_ticks = 0
        while True:
            events = fetch_scan_events_after(record_id, after_id, limit=50)
            if events:
                idle_ticks = 0
                for ev in events:
                    after_id = ev["id"]
                    data = json.dumps({
                        "id": ev["id"],
                        "event_type": ev["event_type"],
                        "payload": ev["payload"],
                        "ts": ev["ts"],
                    })
                    yield f"data: {data}\n\n"
                    if ev["event_type"] == "status" and ev["payload"].get("scan_status") in ("completed", "failed"):
                        yield "data: {\"__done__\": true}\n\n"
                        return
            else:
                idle_ticks += 1
                yield ": heartbeat\n\n"
                if idle_ticks >= 120:
                    return
            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


__all__ = ["scanner_bp"]
