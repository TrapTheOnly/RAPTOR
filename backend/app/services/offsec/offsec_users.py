from flask import current_app, jsonify

from app.repositories.offsec.offsec_records import get_pentest_users_internal
from app.http.decorators.permission_required import permission_required


@permission_required("reassign_pentests_admin")
def get_pentest_users():
    """GET /pentest_users: Get users with pentest role."""
    try:
        users = get_pentest_users_internal()
        return jsonify(users), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching pentest users: {e}")
        return jsonify({"message": "Error fetching pentest users"}), 500


__all__ = ["get_pentest_users"]
