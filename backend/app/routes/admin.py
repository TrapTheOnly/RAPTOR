import sqlite3
import logging
from flask import Blueprint, jsonify, request
from ..services.auth import search_ldap_users
from ..services.admin import change_admin_password, get_existing_users, delete_user, admin_required
from ..services.records import add_user_to_system, update_data
from ..config import DB_PATH
from ..schemas import (
    AddUserSchema,
    ChangePasswordSchema,
    UpdateUserRoleSchema,
    DeleteUserSchema,
    AddIpSourceSchema,
    DeleteIpSourceSchema,
)
from ..schemas.utils import validate_json

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin_routes", __name__)


@admin_bp.route("/ldap-search", methods=["GET"])
@admin_required
def ldap_search():
    """
    Search for users in the LDAP directory.
    """
    query = request.args.get("query").lower()
    try:
        results = search_ldap_users(query)
        return jsonify({"results": results}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/add-user", methods=["POST"])
@admin_required
def add_user():
    """
    Add a user to the allowed_users table.
    """
    payload, error = validate_json(AddUserSchema)
    if error:
        return error

    username = payload.username.lower()
    email = payload.email.lower()
    role = payload.role.lower()

    if role not in ["user", "pentester"]:
        return jsonify({"error": "Invalid role specified."}), 400

    try:
        add_user_to_system(username, email, role)
        return jsonify({"message": f"User {username} added successfully with role {role}."}), 200
    except Exception as e:
        logger.error("Error adding user %s: %s", username, e)
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/change-password", methods=["POST"])
@admin_required
def api_change_password():
    """
    Endpoint to change the admin password.
    """
    payload, error = validate_json(ChangePasswordSchema)
    if error:
        return error

    response, status_code = change_admin_password(
        payload.current_password,
        payload.new_password,
    )
    return jsonify(response), status_code


@admin_bp.route("/existing-users", methods=["GET"])
@admin_required
def api_get_existing_users():
    """
    Endpoint to retrieve existing users.
    """
    response, status_code = get_existing_users()
    return jsonify(response), status_code


@admin_bp.route("/update-user-role", methods=["POST"])
@admin_required
def update_user_role():
    payload, error = validate_json(UpdateUserRoleSchema)
    if error:
        return error

    username = payload.username
    new_role = payload.role

    if new_role not in ["user", "pentester"]:
        return jsonify({"error": "Invalid user role"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE allowed_users SET role = ? WHERE username = ?", (new_role, username))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": f"User {username} not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"message": f"Role for user {username} updated to {new_role}"}), 200
    except Exception as e:
        logger.error("Error updating role for user %s: %s", username, e)
        return jsonify({"error": "Failed to update user role"}), 500


@admin_bp.route("/delete-user", methods=["DELETE"])
@admin_required
def api_delete_user():
    """
    Endpoint to delete a user from the allowed_users table.
    """
    payload, error = validate_json(DeleteUserSchema)
    if error:
        return error

    response, status_code = delete_user(payload.username)
    return jsonify(response), status_code


@admin_bp.route("/manual-update", methods=["POST"])
@admin_required
def manual_update():
    """
    Manually trigger parsing of zone files from the shared folder.
    """
    try:
        update_data()
        return jsonify({"status": "success", "message": "Records updated successfully."}), 200
    except Exception as e:
        logger.error("Manual update error: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route("/ip-sources", methods=["GET"])
@admin_required
def get_ip_sources():
    """
    Returns the full list of IP→Source mappings.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, source_name, ip_address FROM ip_sources")
        rows = c.fetchall()
        conn.close()

        ip_sources = [dict(row) for row in rows]
        return jsonify({"ip_sources": ip_sources}), 200
    except Exception as e:
        logger.error("Error retrieving IP sources: %s", e)
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/ip-sources", methods=["POST"])
@admin_required
def add_ip_source():
    """
    Adds a new IP→Source mapping and updates existing records with that IP.
    """
    payload, error = validate_json(AddIpSourceSchema)
    if error:
        return error

    source_name = payload.source_name
    ip_address = payload.ip_address

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO ip_sources (source_name, ip_address)
            VALUES (?, ?)
        """,
            (source_name, ip_address),
        )
        conn.commit()

        c.execute(
            """
            UPDATE records
            SET source = ?,
                status = 'updated',
                last_modification_date = datetime('now', '+4 hours')
            WHERE ip_address = ?
        """,
            (source_name, ip_address),
        )
        updated_count = c.rowcount

        conn.commit()
        conn.close()

        message = f"IP source {ip_address} added as '{source_name}'. {updated_count} existing record(s) updated."
        logger.info(message)
        return jsonify({"message": message}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": f"IP address {ip_address} is already defined."}), 400
    except Exception as e:
        logger.error("Error adding IP source: %s", e)
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/ip-sources", methods=["DELETE"])
@admin_required
def delete_ip_source():
    """
    Deletes an IP→Source mapping by ip_address and reverts matching records to 'Other'.
    """
    payload, error = validate_json(DeleteIpSourceSchema)
    if error:
        return error

    ip_address = payload.ip_address

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT source_name FROM ip_sources WHERE ip_address = ?", (ip_address,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": f"No mapping found for IP {ip_address}."}), 404

        source_name = row[0]

        c.execute("DELETE FROM ip_sources WHERE ip_address = ?", (ip_address,))
        conn.commit()

        c.execute(
            """
            UPDATE records
            SET source = 'Other',
                status = 'updated',
                last_modification_date = datetime('now', '+4 hours')
            WHERE ip_address = ?
        """,
            (ip_address,),
        )
        updated_count = c.rowcount
        conn.commit()
        conn.close()

        message = (
            f"IP source mapping for {ip_address} ('{source_name}') deleted. "
            f"{updated_count} record(s) reverted to 'Other'."
        )
        logger.info(message)
        return jsonify({"message": message}), 200
    except Exception as e:
        logger.error("Error deleting IP source for %s: %s", ip_address, e)
        return jsonify({"error": str(e)}), 500
