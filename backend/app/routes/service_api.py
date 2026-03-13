from flask import Blueprint, jsonify

from app.http.decorators.service_api_key_required import service_api_key_required
from app.services.service_api_service import get_service_pentests_payload, get_service_records_payload

service_api_bp = Blueprint("service_api", __name__)


@service_api_bp.route("/service-api/v1/records", methods=["GET"])
@service_api_key_required("records.read")
def service_records():
    payload, status_code = get_service_records_payload()
    return jsonify(payload), status_code


@service_api_bp.route("/service-api/v1/pentests", methods=["GET"])
@service_api_key_required("pentests.read")
def service_pentests():
    payload, status_code = get_service_pentests_payload()
    return jsonify(payload), status_code


__all__ = ["service_api_bp"]
