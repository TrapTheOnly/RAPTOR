from flask import Blueprint, jsonify, request, session

from app.http.decorators.admin_required import admin_or_manager_required
from app.http.decorators.permission_required import permission_required
from app.http.request_utils import parse_json_object
from app.services import integrations_service

integrations_bp = Blueprint("integrations", __name__)


@integrations_bp.route("/api/integrations/meta", methods=["GET"])
@permission_required("view_pentest_page")
def integration_meta():
    payload, status_code = integrations_service.catalog()
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/ready", methods=["GET"])
@permission_required("view_pentest_page")
def list_ready_integrations():
    payload, status_code = integrations_service.list_ready(request.args.get("kind"))
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/preview", methods=["POST"])
@permission_required("modify_pentests")
def preview_integration_export():
    payload, status_code = integrations_service.preview_export(parse_json_object())
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/export", methods=["POST"])
@permission_required("modify_pentests")
def run_integration_export():
    payload, status_code = integrations_service.export_findings(
        parse_json_object(), session.get("username") or ""
    )
    return jsonify(payload), status_code


@integrations_bp.route("/api/findings/<finding_id>/exports", methods=["GET"])
@permission_required("view_pentest_page")
def list_finding_exports(finding_id: str):
    payload, status_code = integrations_service.list_finding_exports(finding_id)
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations", methods=["GET"])
@admin_or_manager_required
def list_integrations():
    payload, status_code = integrations_service.list_connections(request.args.get("kind"))
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations", methods=["POST"])
@admin_or_manager_required
def create_integration():
    payload, status_code = integrations_service.create_connection(
        parse_json_object(), session.get("username") or ""
    )
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>", methods=["GET"])
@admin_or_manager_required
def get_integration(connection_id: int):
    payload, status_code = integrations_service.get_connection(connection_id)
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>", methods=["PATCH"])
@admin_or_manager_required
def patch_integration(connection_id: int):
    payload, status_code = integrations_service.update_connection(connection_id, parse_json_object())
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>", methods=["DELETE"])
@admin_or_manager_required
def delete_integration(connection_id: int):
    payload, status_code = integrations_service.delete_connection(connection_id)
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>/test", methods=["POST"])
@admin_or_manager_required
def test_integration(connection_id: int):
    payload, status_code = integrations_service.test_connection(connection_id)
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>/catalog/<resource>", methods=["GET"])
@admin_or_manager_required
def integration_catalog(connection_id: int, resource: str):
    payload, status_code = integrations_service.list_catalog(connection_id, resource, request.args)
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>/templates", methods=["GET"])
@admin_or_manager_required
def list_templates(connection_id: int):
    payload, status_code = integrations_service.list_templates(connection_id)
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>/templates", methods=["POST"])
@admin_or_manager_required
def create_template(connection_id: int):
    payload, status_code = integrations_service.create_template(connection_id, parse_json_object())
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>/templates/<int:template_id>", methods=["PATCH"])
@admin_or_manager_required
def patch_template(connection_id: int, template_id: int):
    payload, status_code = integrations_service.update_template(connection_id, template_id, parse_json_object())
    return jsonify(payload), status_code


@integrations_bp.route("/api/integrations/<int:connection_id>/templates/<int:template_id>", methods=["DELETE"])
@admin_or_manager_required
def delete_template(connection_id: int, template_id: int):
    payload, status_code = integrations_service.delete_template(connection_id, template_id)
    return jsonify(payload), status_code


@integrations_bp.route(
    "/api/integrations/<int:connection_id>/templates/<int:template_id>/mappings",
    methods=["PUT"],
)
@admin_or_manager_required
def save_mappings(connection_id: int, template_id: int):
    payload, status_code = integrations_service.save_mappings(connection_id, template_id, parse_json_object())
    return jsonify(payload), status_code
