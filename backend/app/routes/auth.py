from flask import Blueprint, jsonify, session

from app.http.request_utils import parse_json_object
from app.services import auth_service

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    payload, status_code = auth_service.login(parse_json_object(), session)
    return jsonify(payload), status_code


@auth_bp.route("/session-status", methods=["GET"])
def session_status():
    payload, status_code = auth_service.session_status(session)
    return jsonify(payload), status_code


@auth_bp.route("/session/extend", methods=["POST"])
def extend_logged_in_session():
    payload, status_code = auth_service.extend_logged_in_session(session)
    return jsonify(payload), status_code


@auth_bp.route("/logout", methods=["POST"])
def logout():
    payload, status_code = auth_service.logout(session)
    return jsonify(payload), status_code


@auth_bp.route("/admin-reset-password", methods=["POST"])
def api_admin_reset_password():
    payload, status_code = auth_service.admin_reset_password(parse_json_object(), session)
    return jsonify(payload), status_code


@auth_bp.route("/user-reset-password", methods=["POST"])
def api_user_reset_password():
    payload, status_code = auth_service.user_reset_password(parse_json_object(), session)
    return jsonify(payload), status_code
