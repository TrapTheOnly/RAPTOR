from flask import Blueprint, send_from_directory, current_app
from ..services.auth import login_required_html

frontend_bp = Blueprint("frontend", __name__)


@frontend_bp.route("/")
@login_required_html
def serve_index():
    return send_from_directory(current_app.static_folder, "index.html")


@frontend_bp.app_errorhandler(404)
def not_found(e):
    return send_from_directory(current_app.static_folder, "index.html")
