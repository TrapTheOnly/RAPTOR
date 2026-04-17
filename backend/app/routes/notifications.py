from flask import Blueprint, jsonify, session

from app.http.decorators.login_required import login_required_json
from app.repositories.notifications_repository import (
    delete_all_notifications,
    delete_notification,
    get_notification_count,
    get_notifications_for_user,
)

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications", methods=["GET"])
@login_required_json
def list_notifications():
    username = session.get("username", "")
    if not username:
        return jsonify({"error": "Unauthorized"}), 403
    notifications = get_notifications_for_user(username)
    return jsonify({"notifications": notifications, "count": len(notifications)}), 200


@notifications_bp.route("/notifications/count", methods=["GET"])
@login_required_json
def notification_count():
    username = session.get("username", "")
    if not username:
        return jsonify({"error": "Unauthorized"}), 403
    count = get_notification_count(username)
    return jsonify({"count": count}), 200


@notifications_bp.route("/notifications/<int:notification_id>", methods=["DELETE"])
@login_required_json
def dismiss_notification(notification_id):
    username = session.get("username", "")
    if not username:
        return jsonify({"error": "Unauthorized"}), 403
    deleted = delete_notification(notification_id, username)
    if not deleted:
        return jsonify({"error": "Notification not found."}), 404
    return jsonify({"message": "Notification dismissed."}), 200


@notifications_bp.route("/notifications", methods=["DELETE"])
@login_required_json
def dismiss_all_notifications():
    username = session.get("username", "")
    if not username:
        return jsonify({"error": "Unauthorized"}), 403
    count = delete_all_notifications(username)
    return jsonify({"message": f"{count} notification(s) dismissed."}), 200
