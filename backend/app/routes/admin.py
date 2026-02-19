from flask import Blueprint, jsonify, request

from app.http.request_utils import parse_json_object
from app.services import dns_sync_service, offsec_admin_service, user_admin_service
from app.http.decorators.admin_required import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/ldap-search", methods=["GET"])
@admin_required
def ldap_search():
    payload, status_code = user_admin_service.ldap_search(request.args.get("query", ""))
    return jsonify(payload), status_code


@admin_bp.route("/add-user", methods=["POST"])
@admin_required
def add_user():
    payload, status_code = user_admin_service.add_user(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/add-local-user", methods=["POST"])
@admin_required
def add_local_user():
    payload, status_code = user_admin_service.add_local_user(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/change-password", methods=["POST"])
@admin_required
def api_change_password():
    payload, status_code = user_admin_service.change_password(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/existing-users", methods=["GET"])
@admin_required
def api_get_existing_users():
    payload, status_code = user_admin_service.get_existing_users_service()
    return jsonify(payload), status_code


@admin_bp.route("/update-user-role", methods=["POST"])
@admin_required
def update_user_role():
    payload, status_code = user_admin_service.update_user_role(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/update-user-permissions", methods=["POST"])
@admin_required
def update_user_permissions():
    payload, status_code = user_admin_service.update_user_permissions(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/delete-user", methods=["DELETE"])
@admin_required
def api_delete_user():
    payload, status_code = user_admin_service.delete_user_service(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/manual-update", methods=["POST"])
@admin_required
def manual_update():
    payload, status_code = user_admin_service.manual_update(dns_sync_service.update_data)
    return jsonify(payload), status_code


@admin_bp.route("/pentest/reset-keep-open", methods=["POST"])
@admin_required
def reset_keep_open_vulnerabilities():
    payload, status_code = offsec_admin_service.reset_keep_open_vulnerabilities(parse_json_object())
    return jsonify(payload), status_code
