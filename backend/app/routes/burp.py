from flask import Blueprint, jsonify, request, send_file, session

from app.http.decorators.permission_required import permission_required
from app.http.request_utils import parse_json_object
from app.services import burp_service
from app.services.burp_dist import version_payload

burp_bp = Blueprint("burp", __name__)


def _burp_token() -> str:
    header = str(request.headers.get("X-Burp-Token") or "").strip()
    if header:
        return header
    auth = str(request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _peer_ip() -> str:
    return burp_service.peer_ip_from_request(
        request.headers.get("X-Forwarded-For", ""),
        request.remote_addr or "",
    )


@burp_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/burp-token", methods=["POST"])
@permission_required("modify_pentests")
def mint_burp_token(app_id: int, wave_id: int):
    payload, status_code = burp_service.mint_wave_token(
        app_id,
        wave_id,
        username=str(session.get("username") or ""),
        role=str(session.get("user_type") or ""),
    )
    return jsonify(payload), status_code


@burp_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/burp-token", methods=["DELETE"])
@permission_required("modify_pentests")
def revoke_burp_token(app_id: int, wave_id: int):
    payload, status_code = burp_service.revoke_wave_token(
        app_id,
        wave_id,
        username=str(session.get("username") or ""),
        role=str(session.get("user_type") or ""),
    )
    return jsonify(payload), status_code


@burp_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/burp", methods=["GET"])
@permission_required("view_pentest_page")
def get_wave_burp(app_id: int, wave_id: int):
    payload, status_code = burp_service.wave_burp_status(app_id, wave_id)
    return jsonify(payload), status_code


@burp_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/burp/analyze", methods=["POST"])
@permission_required("modify_pentests")
def start_burp_analyze(app_id: int, wave_id: int):
    from app.services import burp_analyze

    payload, status_code = burp_analyze.queue_analyze_job(
        app_id,
        wave_id,
        username=str(session.get("username") or ""),
        role=str(session.get("user_type") or ""),
    )
    return jsonify(payload), status_code


@burp_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/burp/drafts", methods=["GET"])
@permission_required("view_pentest_page")
def list_burp_drafts(app_id: int, wave_id: int):
    from app.services import burp_evidence

    payload, status_code = burp_evidence.list_drafts_session(
        app_id,
        wave_id,
        username=str(session.get("username") or ""),
        role=str(session.get("user_type") or ""),
    )
    return jsonify(payload), status_code


@burp_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/burp/evidence", methods=["POST"])
@permission_required("modify_pentests")
def file_burp_evidence(app_id: int, wave_id: int):
    from app.services import burp_evidence

    payload, status_code = burp_evidence.file_evidence_session(
        app_id,
        wave_id,
        username=str(session.get("username") or ""),
        role=str(session.get("user_type") or ""),
        data=parse_json_object(),
    )
    return jsonify(payload), status_code


@burp_bp.route("/api/apps/<int:app_id>/waves/<int:wave_id>/burp/propose", methods=["POST"])
@permission_required("modify_pentests")
def propose_burp_scanner(app_id: int, wave_id: int):
    from app.services import burp_evidence

    payload, status_code = burp_evidence.propose_scanner(
        app_id,
        wave_id,
        username=str(session.get("username") or ""),
        role=str(session.get("user_type") or ""),
        data=parse_json_object(),
    )
    return jsonify(payload), status_code


@burp_bp.route("/burp/v1/enroll", methods=["POST"])
def burp_enroll():
    payload, status_code = burp_service.enroll_agent_service(parse_json_object(), last_seen_ip=_peer_ip())
    return jsonify(payload), status_code


@burp_bp.route("/burp/v1/heartbeat", methods=["POST"])
def burp_heartbeat():
    agent = burp_service.authenticate_burp_token(_burp_token())
    if not agent:
        return jsonify({"error": "Unauthorized access."}), 401
    payload, status_code = burp_service.heartbeat_service(agent, parse_json_object(), last_seen_ip=_peer_ip())
    return jsonify(payload), status_code


@burp_bp.route("/burp/v1/ingest", methods=["POST"])
def burp_ingest():
    agent = burp_service.authenticate_burp_token(_burp_token())
    if not agent:
        return jsonify({"error": "Unauthorized access."}), 401
    payload, status_code = burp_service.ingest_service(agent, parse_json_object(), last_seen_ip=_peer_ip())
    return jsonify(payload), status_code


@burp_bp.route("/burp/v1/auth-template", methods=["POST"])
def burp_auth_template():
    agent = burp_service.authenticate_burp_token(_burp_token())
    if not agent:
        return jsonify({"error": "Unauthorized access."}), 401
    payload, status_code = burp_service.store_auth_template(agent, parse_json_object())
    return jsonify(payload), status_code


@burp_bp.route("/burp/v1/jwt", methods=["POST"])
def burp_jwt():
    agent = burp_service.authenticate_burp_token(_burp_token())
    if not agent:
        return jsonify({"error": "Unauthorized access."}), 401
    payload, status_code = burp_service.enqueue_jwt(agent, parse_json_object())
    return jsonify(payload), status_code


@burp_bp.route("/burp/v1/drafts", methods=["GET"])
def burp_drafts():
    from app.services import burp_evidence

    agent = burp_service.authenticate_burp_token(_burp_token())
    if not agent:
        return jsonify({"error": "Unauthorized access."}), 401
    payload, status_code = burp_evidence.list_drafts_for_agent(agent)
    return jsonify(payload), status_code


@burp_bp.route("/burp/v1/evidence", methods=["POST"])
def burp_evidence():
    from app.services import burp_evidence as evidence_service

    agent = burp_service.authenticate_burp_token(_burp_token())
    if not agent:
        return jsonify({"error": "Unauthorized access."}), 401
    payload, status_code = evidence_service.file_evidence_for_agent(agent, parse_json_object())
    return jsonify(payload), status_code


@burp_bp.route("/burp/v1/version", methods=["GET"])
def burp_version():
    return jsonify(version_payload()), 200


@burp_bp.route("/burp/v1/download/raptor-burp.jar", methods=["GET"])
def burp_download_jar():
    path = burp_service.download_jar()
    if not path:
        return jsonify({"error": "Burp extension is not available. Rebuild RAPTOR with the Burp JAR."}), 404
    return send_file(path, as_attachment=True, download_name=path.name, mimetype="application/java-archive")
