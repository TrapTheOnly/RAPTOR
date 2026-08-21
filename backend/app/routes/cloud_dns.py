from flask import Blueprint, jsonify, session

from app.http.decorators.admin_required import admin_required
from app.http.request_utils import parse_json_object
from app.services import cloud_dns_service

cloud_dns_bp = Blueprint("cloud_dns", __name__)


@cloud_dns_bp.route("/admin/dns-sources", methods=["GET"])
@admin_required
def admin_list_dns_sources():
    payload, status_code = cloud_dns_service.list_cloud_sources_service()
    return jsonify(payload), status_code


@cloud_dns_bp.route("/admin/dns-sources", methods=["POST"])
@admin_required
def admin_create_dns_source():
    payload, status_code = cloud_dns_service.create_cloud_source_service(
        parse_json_object(),
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@cloud_dns_bp.route("/admin/dns-sources/<int:source_id>", methods=["PATCH"])
@admin_required
def admin_update_dns_source(source_id: int):
    payload, status_code = cloud_dns_service.update_cloud_source_service(
        source_id,
        parse_json_object(),
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@cloud_dns_bp.route("/admin/dns-sources/<int:source_id>", methods=["DELETE"])
@admin_required
def admin_delete_dns_source(source_id: int):
    payload, status_code = cloud_dns_service.delete_cloud_source_service(
        source_id,
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@cloud_dns_bp.route("/admin/dns-sources/<int:source_id>/zones", methods=["GET"])
@admin_required
def admin_list_dns_source_zones(source_id: int):
    payload, status_code = cloud_dns_service.list_source_zones_service(source_id)
    return jsonify(payload), status_code


@cloud_dns_bp.route("/admin/dns-sources/<int:source_id>/sync-now", methods=["POST"])
@admin_required
def admin_sync_dns_source(source_id: int):
    payload, status_code = cloud_dns_service.sync_now_service(
        source_id,
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code
