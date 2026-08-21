from flask import Blueprint, jsonify, redirect, request, session

from app.http.request_utils import parse_json_object
from app.services import auth_service
from app.services.sso_auth_service import authorization_url, complete_sso_callback
from app.services.sso_settings_service import list_login_providers

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


@auth_bp.route("/auth/sso/providers", methods=["GET"])
def sso_login_providers():
    payload, status_code = list_login_providers()
    return jsonify(payload), status_code


@auth_bp.route("/auth/sso/<string:alias>/start", methods=["GET"])
def sso_start(alias: str):
    url, error = authorization_url(alias, session)
    if error or not url:
        return redirect(f"/login?sso_error={error or 'unsupported'}")
    return redirect(url)


@auth_bp.route("/auth/sso/callback", methods=["GET"])
def sso_callback():
    target, error = complete_sso_callback(session, request.args)
    if error:
        return redirect(f"/login?sso_error={error}")
    return redirect(target)


@auth_bp.route("/admin-reset-password", methods=["POST"])
def api_admin_reset_password():
    payload, status_code = auth_service.admin_reset_password(parse_json_object(), session)
    return jsonify(payload), status_code


@auth_bp.route("/user-reset-password", methods=["POST"])
def api_user_reset_password():
    payload, status_code = auth_service.user_reset_password(parse_json_object(), session)
    return jsonify(payload), status_code
