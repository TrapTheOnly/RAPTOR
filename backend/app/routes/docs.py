from flask import Blueprint, jsonify, session

from app.services.docs_manifest_service import (
    get_docs_access_matrix_for_user,
    get_docs_manifest_for_user,
    get_docs_page_for_user,
)
from app.http.decorators.login_required import login_required_json

docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/docs/manifest", methods=["GET"])
@login_required_json
def docs_manifest():
    response, status_code = get_docs_manifest_for_user(
        session.get("username"),
        session.get("user_type"),
    )
    return jsonify(response), status_code


@docs_bp.route("/docs/content/<string:section_slug>/<string:page_slug>", methods=["GET"])
@login_required_json
def docs_page_content(section_slug: str, page_slug: str):
    response, status_code = get_docs_page_for_user(
        section_slug=section_slug,
        page_slug=page_slug,
        username=session.get("username"),
        role=session.get("user_type"),
    )
    return jsonify(response), status_code


@docs_bp.route("/docs/access-matrix", methods=["GET"])
@login_required_json
def docs_access_matrix():
    response, status_code = get_docs_access_matrix_for_user(
        session.get("username"),
        session.get("user_type"),
    )
    return jsonify(response), status_code
