import logging
import re
import sqlite3
from typing import Any, Dict, Optional, Tuple

from app.repositories import applications_repository
from app.repositories import records_repository

logger = logging.getLogger(__name__)


def _sanitize_record_string(raw_value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9\.\-_ ]+", "", str(raw_value or ""))


def _sanitize_app_name(raw_value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9\-_. ]+", "", str(raw_value or "").strip())


def get_dashboard_data() -> Tuple[Dict[str, Any], int]:
    try:
        return records_repository.fetch_dashboard_data(), 200
    except Exception as e:
        logger.error(f"Error fetching dashboard datasets: {e}")
        return {"error": "Failed to load dashboard data."}, 500


def get_records() -> Any:
    return records_repository.fetch_records()


def update_record(record_id: int, data: Dict[str, Any], username: str) -> Tuple[Dict[str, Any], int]:
    if not data:
        return {"error": "Invalid JSON payload."}, 400

    try:
        application_owner = _sanitize_record_string(data.get("application_owner", ""))
        maintainer = _sanitize_record_string(data.get("maintainer", ""))
        open_ports = data.get("open_ports", "")
        description = data.get("description", "")
        raw_application_id = data.get("application_id")
        application_id = None
        if raw_application_id not in (None, "", "null"):
            try:
                application_id = int(raw_application_id)
            except (TypeError, ValueError):
                return {"error": "Invalid application ID."}, 400

        result = records_repository.update_record(
            record_id=record_id,
            application_owner=application_owner,
            maintainer=maintainer,
            description=description,
            open_ports=open_ports,
            application_id=application_id,
            username=username,
        )
        if result == "application_not_found":
            return {"error": "Application not found."}, 404
        if result == "record_not_found":
            return {"error": "Record not found"}, 404

        return {"status": "success"}, 200
    except Exception as e:
        logger.error(f"Error updating record {record_id}: {e}")
        return {"error": "Failed to update record."}, 400


def get_applications() -> Tuple[Any, int]:
    try:
        return applications_repository.fetch_applications(), 200
    except Exception as e:
        logger.error(f"Error fetching applications: {e}")
        return {"error": "Failed to fetch applications."}, 500


def create_application(data: Dict[str, Any], username: str) -> Tuple[Dict[str, Any], int]:
    if not data:
        return {"error": "Invalid JSON payload."}, 400

    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "Application name is required."}, 400

    sanitized = _sanitize_app_name(name)
    if not sanitized:
        return {"error": "Invalid application name."}, 400

    try:
        applications_repository.create_application(sanitized, username)
        return {"message": "Application created.", "name": sanitized}, 201
    except sqlite3.IntegrityError:
        return {"error": "Application name already exists."}, 409
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        return {"error": "Failed to create application."}, 500


def update_application(app_id: int, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    if not data:
        return {"error": "Invalid JSON payload."}, 400

    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "Application name is required."}, 400

    sanitized = _sanitize_app_name(name)
    if not sanitized:
        return {"error": "Invalid application name."}, 400

    try:
        exists = applications_repository.update_application(app_id, sanitized)
        if not exists:
            return {"error": "Application not found."}, 404
        return {"message": "Application updated.", "name": sanitized}, 200
    except sqlite3.IntegrityError:
        return {"error": "Application name already exists."}, 409
    except Exception as e:
        logger.error(f"Error updating application: {e}")
        return {"error": "Failed to update application."}, 500


def delete_application(app_id: int) -> Tuple[Dict[str, Any], int]:
    try:
        exists = applications_repository.delete_application(app_id)
        if not exists:
            return {"error": "Application not found."}, 404
        return {"message": "Application deleted."}, 200
    except Exception as e:
        logger.error(f"Error deleting application: {e}")
        return {"error": "Failed to delete application."}, 500


def delete_record(record_id: int, username: str) -> Tuple[Dict[str, Any], int]:
    try:
        deleted = records_repository.delete_record(record_id, username)
        if not deleted:
            return {"error": "Record not found"}, 404
        return {"status": "success", "message": f"Record {record_id} deleted"}, 200
    except Exception as e:
        logger.error(f"Error deleting record {record_id}: {e}")
        return {"status": "error", "message": "Failed to delete record."}, 400


def get_record_history(record_id: int) -> Any:
    return records_repository.fetch_record_history(record_id)


def get_record_by_id(record_id: int) -> Tuple[Dict[str, Any], int]:
    row = records_repository.fetch_record_by_id(record_id)
    if row:
        return row, 200
    return {"error": "Record not found"}, 404


def get_record_by_domain(domain: str) -> Tuple[Dict[str, Any], int]:
    row = records_repository.fetch_record_by_domain(domain)
    if row:
        return row, 200
    return {"error": "Record not found"}, 404
