from flask import Blueprint, jsonify, session

from app.http.request_utils import parse_json_object
from app.services import records_service
from app.http.decorators.admin_required import admin_or_manager_required
from app.http.decorators.permission_required import permission_required

records_bp = Blueprint("records", __name__)


@records_bp.route("/dashboard/data", methods=["GET"])
@permission_required("view_dashboard")
def get_dashboard_data():
    payload, status_code = records_service.get_dashboard_data()
    return jsonify(payload), status_code


@records_bp.route("/api/records", methods=["GET"])
@permission_required("view_records")
def get_records():
    return jsonify(records_service.get_records())


@records_bp.route("/api/records", methods=["POST"])
@permission_required("create_manual_records")
def create_record():
    payload, status_code = records_service.create_manual_record(
        parse_json_object(),
        session.get("username", "unknown"),
    )
    return jsonify(payload), status_code


@records_bp.route("/api/records/<int:record_id>", methods=["POST"])
@permission_required("modify_records")
def update_record(record_id: int):
    payload, status_code = records_service.update_record(
        record_id=record_id,
        data=parse_json_object(),
        username=session["username"],
    )
    return jsonify(payload), status_code


@records_bp.route("/api/apps", methods=["GET"])
@permission_required("view_records")
def get_applications():
    payload, status_code = records_service.get_applications()
    return jsonify(payload), status_code


@records_bp.route("/api/apps", methods=["POST"])
@permission_required("manage_apps")
def create_application():
    payload, status_code = records_service.create_application(
        parse_json_object(), session.get("username", "unknown")
    )
    return jsonify(payload), status_code


@records_bp.route("/api/apps/<int:app_id>", methods=["PUT"])
@permission_required("manage_apps")
def update_application(app_id: int):
    payload, status_code = records_service.update_application(app_id, parse_json_object())
    return jsonify(payload), status_code


@records_bp.route("/api/apps/<int:app_id>", methods=["DELETE"])
@permission_required("manage_apps")
def delete_application(app_id: int):
    payload, status_code = records_service.delete_application(app_id)
    return jsonify(payload), status_code


@records_bp.route("/api/records/<int:record_id>", methods=["DELETE"])
@permission_required("delete_records")
def delete_record(record_id: int):
    payload, status_code = records_service.delete_record(record_id, session["username"])
    return jsonify(payload), status_code


@records_bp.route("/api/records/<int:record_id>/resolve-sync-conflict", methods=["POST"])
@admin_or_manager_required
def resolve_sync_conflict(record_id: int):
    payload, status_code = records_service.resolve_sync_conflict(
        record_id,
        session.get("username", "unknown"),
        parse_json_object(),
    )
    return jsonify(payload), status_code


@records_bp.route("/api/records/<int:record_id>/history", methods=["GET"])
@permission_required("view_record_details")
def get_record_history(record_id: int):
    return jsonify(records_service.get_record_history(record_id))


@records_bp.route("/api/records/<int:record_id>", methods=["GET"])
@permission_required("view_record_details")
def get_record_by_id(record_id: int):
    payload, status_code = records_service.get_record_by_id(record_id)
    return jsonify(payload), status_code


@records_bp.route("/api/records/<string:domain>", methods=["GET"])
@permission_required("view_record_details")
def get_record_by_domain(domain: str):
    payload, status_code = records_service.get_record_by_domain(domain)
    return jsonify(payload), status_code
