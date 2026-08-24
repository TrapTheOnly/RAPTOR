from flask import Blueprint, jsonify, session, request, Response

from app.http.request_utils import parse_json_object
from app.services import offsec_admin_service, service_account_service, sso_settings_service, user_admin_service
from app.http.decorators.admin_required import admin_required
from app.repositories.email_config_repository import get_email_config, upsert_email_config
from app.integrations.email.client import send_email, test_smtp_connection

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


@admin_bp.route("/sso/connections", methods=["GET"])
@admin_required
def list_sso_connections():
    payload, status_code = sso_settings_service.list_connections()
    return jsonify(payload), status_code


@admin_bp.route("/sso/connections", methods=["POST"])
@admin_required
def create_sso_connection():
    payload, status_code = sso_settings_service.create_connection(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/sso/connections/<string:alias>", methods=["GET"])
@admin_required
def get_sso_connection(alias: str):
    payload, status_code = sso_settings_service.get_connection(alias)
    return jsonify(payload), status_code


@admin_bp.route("/sso/connections/<string:alias>", methods=["PUT"])
@admin_required
def update_sso_connection(alias: str):
    payload, status_code = sso_settings_service.update_connection(alias, parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/sso/connections/<string:alias>", methods=["DELETE"])
@admin_required
def delete_sso_connection(alias: str):
    payload, status_code = sso_settings_service.delete_connection(alias)
    return jsonify(payload), status_code


@admin_bp.route("/sso/connections/<string:alias>/test", methods=["POST"])
@admin_required
def test_sso_connection(alias: str):
    payload, status_code = sso_settings_service.test_connection(alias)
    return jsonify(payload), status_code


@admin_bp.route("/sso/connections/<string:alias>/sp-metadata", methods=["GET"])
@admin_required
def download_sso_sp_metadata(alias: str):
    body, status_code, content_type = sso_settings_service.fetch_sp_metadata(alias)
    if status_code != 200:
        return jsonify(body), status_code
    filename = f"{alias}-sp-metadata.xml"
    return Response(
        body,
        status=200,
        mimetype=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_bp.route("/sso/allowlist", methods=["POST"])
@admin_required
def preprovision_sso_user():
    payload, status_code = user_admin_service.preprovision_sso_user(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/pentest/reset-keep-open", methods=["POST"])
@admin_required
def reset_keep_open_vulnerabilities():
    payload, status_code = offsec_admin_service.reset_keep_open_vulnerabilities(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/service-accounts", methods=["GET"])
@admin_required
def list_service_accounts():
    payload, status_code = service_account_service.get_service_accounts_service()
    return jsonify(payload), status_code


@admin_bp.route("/service-accounts", methods=["POST"])
@admin_required
def create_service_account():
    payload, status_code = service_account_service.create_service_account_service(parse_json_object())
    return jsonify(payload), status_code


@admin_bp.route("/service-accounts/<string:username>/api-key", methods=["POST"])
@admin_required
def create_service_account_api_key(username: str):
    payload, status_code = service_account_service.create_service_account_key_service(
        username=username,
        data=parse_json_object(),
        actor_username=session.get("username", ""),
    )
    return jsonify(payload), status_code


@admin_bp.route("/service-accounts/<string:username>/api-key", methods=["GET"])
@admin_required
def view_service_account_api_key(username: str):
    payload, status_code = service_account_service.view_service_account_key_service(username)
    return jsonify(payload), status_code


@admin_bp.route("/service-accounts/<string:username>/api-key/rotate", methods=["POST"])
@admin_required
def rotate_service_account_api_key(username: str):
    payload, status_code = service_account_service.rotate_service_account_key_service(
        username=username,
        actor_username=session.get("username", ""),
    )
    return jsonify(payload), status_code


@admin_bp.route("/service-accounts/<string:username>/privileges", methods=["PUT"])
@admin_required
def update_service_account_privileges(username: str):
    payload, status_code = service_account_service.update_service_account_scopes_service(
        username=username,
        data=parse_json_object(),
    )
    return jsonify(payload), status_code


@admin_bp.route("/admin/email-config", methods=["GET"])
@admin_required
def api_get_email_config():
    config = get_email_config()
    if not config:
        return jsonify({"config": None}), 200
    safe_config = dict(config)
    if safe_config.get("smtp_password"):
        safe_config["smtp_password"] = "••••••••"
    return jsonify({"config": safe_config}), 200


@admin_bp.route("/admin/email-config", methods=["POST"])
@admin_required
def api_save_email_config():
    data = parse_json_object()
    required = ["smtp_host", "smtp_port", "sender_email"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required."}), 400

    existing = get_email_config()
    if data.get("smtp_password") == "••••••••" and existing:
        data["smtp_password"] = existing.get("smtp_password", "")

    data["updated_by"] = session.get("username", "")
    upsert_email_config(data)
    return jsonify({"message": "Email configuration saved."}), 200


@admin_bp.route("/admin/email-config/test-connection", methods=["POST"])
@admin_required
def api_test_smtp_connection():
    config = get_email_config()
    if not config:
        return jsonify({"error": "No email configuration found. Save settings first."}), 400
    success, message = test_smtp_connection(config)
    if success:
        return jsonify({"message": message}), 200
    return jsonify({"error": message}), 500


@admin_bp.route("/admin/email-config/test", methods=["POST"])
@admin_required
def api_test_email():
    config = get_email_config()
    if not config:
        return jsonify({"error": "No email configuration found. Save settings first."}), 400

    data = parse_json_object()
    to_email = (data.get("to_email") or "").strip()
    if not to_email or "@" not in to_email:
        return jsonify({"error": "A valid recipient email address is required."}), 400

    body = """
    <html><body style="font-family: sans-serif; padding: 20px;">
        <h2 style="color: #1976d2;">RAPTOR Test Email</h2>
        <p>This is a test email from RAPTOR to verify your SMTP notification settings are working correctly.</p>
    </body></html>
    """
    success = send_email(to_email, "RAPTOR: Test Email", body, config)
    if success:
        return jsonify({"message": f"Test email sent to {to_email}."}), 200
    return jsonify({"error": "Failed to send test email. Check SMTP settings and server logs."}), 500
