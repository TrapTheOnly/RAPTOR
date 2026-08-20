from flask import Blueprint, jsonify, request

from app.http.decorators.internal_api_required import internal_api_required
from app.services.service_api_service import (
    append_vulnerability_payload,
    get_checklist_templates_payload,
    get_service_pentests_payload,
    get_service_records_payload,
    get_single_pentest_payload,
    notify_scan_complete_payload,
    patch_pentest_payload,
    reset_scan_payload,
    set_scan_status_payload,
)
from app.services.scan_events_service import append_scan_event_payload

service_api_bp = Blueprint("service_api", __name__)


@service_api_bp.route("/service-api/v1/records", methods=["GET"])
@internal_api_required
def service_records():
    payload, status_code = get_service_records_payload(
        request.args.get("limit"),
        request.args.get("offset"),
    )
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests", methods=["GET"])
@internal_api_required
def service_pentests():
    payload, status_code = get_service_pentests_payload(
        request.args.get("limit"),
        request.args.get("offset"),
    )
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests/<int:record_id>", methods=["GET"])
@internal_api_required
def service_get_pentest(record_id):
    payload, status_code = get_single_pentest_payload(record_id)
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests/<int:record_id>", methods=["PATCH"])
@internal_api_required
def service_patch_pentest(record_id):
    fields = request.get_json(silent=True) or {}
    payload, status_code = patch_pentest_payload(record_id, fields)
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests/<int:record_id>/scan-status", methods=["PUT"])
@internal_api_required
def service_set_scan_status(record_id):
    body = request.get_json(silent=True) or {}
    payload, status_code = set_scan_status_payload(record_id, str(body.get("scan_status", "")))
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests/<int:record_id>/vulnerabilities", methods=["POST"])
@internal_api_required
def service_append_vulnerability(record_id):
    body = request.get_json(silent=True) or {}
    payload, status_code = append_vulnerability_payload(record_id, body)
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests/<int:record_id>/notify-scan-complete", methods=["POST"])
@internal_api_required
def service_notify_scan_complete(record_id):
    body = request.get_json(silent=True) or {}
    payload, status_code = notify_scan_complete_payload(
        record_id=record_id,
        findings_count=int(body.get("findings_count", 0)),
        input_tokens=int(body.get("input_tokens", 0)),
        output_tokens=int(body.get("output_tokens", 0)),
        cache_read_input_tokens=int(body.get("cache_read_input_tokens", 0)),
        cache_creation_input_tokens=int(body.get("cache_creation_input_tokens", 0)),
        cost_usd=float(body.get("cost_usd", 0.0)),
    )
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests/<int:record_id>/scan-events", methods=["POST"])
@internal_api_required
def service_append_scan_event(record_id):
    body = request.get_json(silent=True) or {}
    raw_job_id = body.get("job_id")
    try:
        job_id = int(raw_job_id) if raw_job_id not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        job_id = None
    payload, status_code = append_scan_event_payload(
        record_id=record_id,
        event_type=str(body.get("event_type", "")),
        event_payload=body.get("payload", {}),
        job_id=job_id,
    )
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests/<int:record_id>/reset-scan", methods=["POST"])
@internal_api_required
def service_reset_scan(record_id):
    payload, status_code = reset_scan_payload(record_id)
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/checklist-templates", methods=["GET"])
@internal_api_required
def service_checklist_templates():
    payload, status_code = get_checklist_templates_payload()
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/vuln-categories", methods=["GET"])
@internal_api_required
def service_list_vuln_categories():
    from app.services.metadata_service import get_vuln_categories
    payload, status_code = get_vuln_categories()
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/vuln-categories", methods=["POST"])
@internal_api_required
def service_create_vuln_category():
    from app.services.metadata_service import add_vuln_category
    body = request.get_json(silent=True) or {}
    payload, status_code = add_vuln_category(body, "RAPTOR-Scanner")
    return jsonify(payload), status_code


__all__ = ["service_api_bp"]
