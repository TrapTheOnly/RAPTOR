from flask import Blueprint, Response, jsonify, session

from app.http.decorators.admin_required import admin_required
from app.http.decorators.login_required import login_required_json
from app.http.request_utils import parse_json_object
from app.services.llm import connections_service
from app.services.llm.local_llm_service import (
    cancel_local_service,
    get_local_status_service,
    install_local_service,
    iter_local_events,
    pause_local_service,
    resume_local_service,
    start_local_service,
    stop_local_service,
    uninstall_local_service,
)
from app.services.llm.recipes import PROVIDERS, USER_CREATABLE_TYPES

llm_bp = Blueprint("llm", __name__)


@llm_bp.route("/admin/llm/providers", methods=["GET"])
@login_required_json
@admin_required
def list_llm_providers():
    providers = []
    for key in USER_CREATABLE_TYPES:
        recipe = PROVIDERS[key]
        providers.append(
            {
                "type": key,
                "label": recipe.get("label"),
                "protocol": recipe.get("protocol"),
                "catalog": bool(recipe.get("catalog")),
                "suggested_models": recipe.get("suggested_models") or [],
            }
        )
    return jsonify({"providers": providers}), 200


@llm_bp.route("/admin/llm/connections", methods=["GET"])
@login_required_json
@admin_required
def list_llm_connections():
    payload, status_code = connections_service.list_connections_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/connections", methods=["POST"])
@login_required_json
@admin_required
def create_llm_connection():
    payload, status_code = connections_service.create_connection_service(
        parse_json_object(),
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/connections/<int:connection_id>", methods=["GET"])
@login_required_json
@admin_required
def get_llm_connection(connection_id: int):
    payload, status_code = connections_service.get_connection_service(connection_id)
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/connections/<int:connection_id>", methods=["PATCH"])
@login_required_json
@admin_required
def update_llm_connection(connection_id: int):
    payload, status_code = connections_service.update_connection_service(
        connection_id,
        parse_json_object(),
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/connections/<int:connection_id>", methods=["DELETE"])
@login_required_json
@admin_required
def delete_llm_connection(connection_id: int):
    payload, status_code = connections_service.delete_connection_service(
        connection_id,
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/connections/<int:connection_id>/test", methods=["POST"])
@login_required_json
@admin_required
def test_llm_connection(connection_id: int):
    payload, status_code = connections_service.test_connection_service(
        connection_id,
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/connections/<int:connection_id>/refresh-models", methods=["POST"])
@login_required_json
@admin_required
def refresh_llm_models(connection_id: int):
    payload, status_code = connections_service.refresh_models_service(
        connection_id,
        str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local", methods=["GET"])
@login_required_json
@admin_required
def get_local_llm():
    payload, status_code = get_local_status_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local/install", methods=["POST"])
@login_required_json
@admin_required
def install_local_llm():
    payload, status_code = install_local_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local/cancel", methods=["POST"])
@login_required_json
@admin_required
def cancel_local_llm():
    payload, status_code = cancel_local_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local/pause", methods=["POST"])
@login_required_json
@admin_required
def pause_local_llm():
    payload, status_code = pause_local_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local/resume", methods=["POST"])
@login_required_json
@admin_required
def resume_local_llm():
    payload, status_code = resume_local_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local/start", methods=["POST"])
@login_required_json
@admin_required
def start_local_llm():
    payload, status_code = start_local_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local/stop", methods=["POST"])
@login_required_json
@admin_required
def stop_local_llm():
    payload, status_code = stop_local_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local/uninstall", methods=["POST"])
@login_required_json
@admin_required
def uninstall_local_llm():
    payload, status_code = uninstall_local_service()
    return jsonify(payload), status_code


@llm_bp.route("/admin/llm/local/events", methods=["GET"])
@login_required_json
@admin_required
def local_llm_events():
    return Response(
        iter_local_events(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["llm_bp"]
