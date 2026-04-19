from flask import Blueprint, jsonify, session

from app.http.request_utils import parse_json_object
from app.services import metadata_service
from app.http.decorators.permission_required import permission_required

metadata_bp = Blueprint("metadata", __name__)


@metadata_bp.route("/ip-sources", methods=["GET"])
@permission_required("manage_ip_sources")
def get_ip_sources():
    payload, status_code = metadata_service.get_ip_sources()
    return jsonify(payload), status_code


@metadata_bp.route("/ip-sources", methods=["POST"])
@permission_required("manage_ip_sources")
def add_ip_source():
    payload, status_code = metadata_service.add_ip_source(parse_json_object())
    return jsonify(payload), status_code


@metadata_bp.route("/ip-sources", methods=["DELETE"])
@permission_required("manage_ip_sources")
def delete_ip_source():
    payload, status_code = metadata_service.delete_ip_source(parse_json_object())
    return jsonify(payload), status_code


@metadata_bp.route("/vuln-categories", methods=["GET"])
@permission_required("view_pentest_page")
def get_vuln_categories():
    payload, status_code = metadata_service.get_vuln_categories()
    return jsonify(payload), status_code


@metadata_bp.route("/vuln-categories", methods=["POST"])
@permission_required("manage_vuln_categories")
def add_vuln_category():
    payload, status_code = metadata_service.add_vuln_category(
        parse_json_object(), session.get("username", "unknown")
    )
    return jsonify(payload), status_code


@metadata_bp.route("/vuln-categories/<int:category_id>", methods=["DELETE"])
@permission_required("manage_vuln_categories")
def delete_vuln_category(category_id: int):
    payload, status_code = metadata_service.delete_vuln_category(category_id)
    return jsonify(payload), status_code
