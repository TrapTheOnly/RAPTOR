import logging
import re
from typing import Any, Dict, Optional, Tuple

from app.integrations.db.connection import IntegrityError
from app.services import dns_sync_service
from app.repositories import applications_repository
from app.repositories import records_repository

logger = logging.getLogger(__name__)


def _sanitize_record_string(raw_value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9\.\-_ ]+", "", str(raw_value or ""))


def _sanitize_app_name(raw_value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9\-_. ]+", "", str(raw_value or "").strip())


def _normalize_domain_name(raw_value: Any) -> str:
    value = str(raw_value or "").strip().lower().rstrip(".")
    if not value or len(value) > 253:
        return ""
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9\-\.]{0,251}[a-z0-9])?", value):
        return ""
    labels = value.split(".")
    if len(labels) < 2:
        return ""
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        return ""
    return value


def _normalize_ip_address(raw_value: Any) -> str:
    value = str(raw_value or "").strip()
    if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
        return ""
    octets = value.split(".")
    if any(int(octet) > 255 for octet in octets):
        return ""
    return value


def get_dashboard_data() -> Tuple[Dict[str, Any], int]:
    try:
        return records_repository.fetch_dashboard_data(), 200
    except Exception as e:
        logger.error(f"Error fetching dashboard datasets: {e}")
        return {"error": "Failed to load dashboard data."}, 500


def get_records() -> Any:
    return records_repository.fetch_records()


def create_manual_record(data: Dict[str, Any], username: str) -> Tuple[Dict[str, Any], int]:
    if not data:
        return {"error": "Invalid JSON payload."}, 400

    name = _normalize_domain_name(data.get("name"))
    ip_address = _normalize_ip_address(data.get("ip_address"))
    if not name:
        return {"error": "Valid domain name is required."}, 400
    if not ip_address:
        return {"error": "Valid IPv4 address is required."}, 400

    application_owner = _sanitize_record_string(data.get("application_owner", ""))
    maintainer = _sanitize_record_string(data.get("maintainer", ""))
    description = str(data.get("description", "") or "")
    open_ports = str(data.get("open_ports", "") or "")

    raw_application_id = data.get("application_id")
    application_id = None
    if raw_application_id not in (None, "", "null"):
        try:
            application_id = int(raw_application_id)
        except (TypeError, ValueError):
            return {"error": "Invalid application ID."}, 400
    raw_environment_id = data.get("environment_id")
    environment_id = None
    if raw_environment_id not in (None, "", "null"):
        try:
            environment_id = int(raw_environment_id)
        except (TypeError, ValueError):
            return {"error": "Invalid environment ID."}, 400

    try:
        created = records_repository.create_manual_record(
            name=name,
            ip_address=ip_address,
            application_owner=application_owner,
            maintainer=maintainer,
            description=description,
            open_ports=open_ports,
            application_id=application_id,
            username=username,
            environment_id=environment_id,
        )
    except ValueError:
        return {"error": "Application not found."}, 404
    except IntegrityError:
        return {"error": "Record already exists."}, 409
    except Exception as e:
        logger.error(f"Error creating manual record {name}: {e}")
        return {"error": "Failed to create manual record."}, 500

    row = records_repository.fetch_record_by_id(created["id"])
    if not row:
        return {"error": "Manual record created but could not be loaded."}, 500
    return {"status": "success", "record": row}, 201


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
        raw_environment_id = data.get("environment_id")
        environment_id = None
        if raw_environment_id not in (None, "", "null"):
            try:
                environment_id = int(raw_environment_id)
            except (TypeError, ValueError):
                return {"error": "Invalid environment ID."}, 400

        result = records_repository.update_record(
            record_id=record_id,
            application_owner=application_owner,
            maintainer=maintainer,
            description=description,
            open_ports=open_ports,
            application_id=application_id,
            username=username,
            environment_id=environment_id,
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
    except IntegrityError:
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
        extra = {
            key: data.get(key)
            for key in (
                "owner",
                "data_class",
                "roe_link",
                "cookie_domain",
                "idp",
                "token_audience",
                "app_lead",
            )
            if key in (data or {})
        }
        exists = applications_repository.update_application(app_id, sanitized, extra_fields=extra)
        if not exists:
            return {"error": "Application not found."}, 404
        return {"message": "Application updated.", "name": sanitized}, 200
    except IntegrityError:
        return {"error": "Application name already exists."}, 409
    except Exception as e:
        logger.error(f"Error updating application: {e}")
        return {"error": "Failed to update application."}, 500


def delete_application(app_id: int) -> Tuple[Dict[str, Any], int]:
    try:
        result = applications_repository.delete_application(app_id)
        if result == "not_found":
            return {"error": "Application not found."}, 404
        if result == "in_use":
            return {"error": "Application has in-scope hosts, findings, or exports."}, 409
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


def resolve_sync_conflict(record_id: int, username: str) -> Tuple[Dict[str, Any], int]:
    row = records_repository.fetch_record_by_id(record_id)
    if not row:
        return {"error": "Record not found"}, 404
    if row.get("origin") != "manual" or not bool(row.get("sync_conflict")):
        return {"error": "Record does not have a resolvable sync conflict."}, 409

    imported = dns_sync_service.find_live_imported_record(row.get("name"))
    if not imported:
        return {"error": "Imported domain is not currently available in live zone data."}, 409

    result = records_repository.resolve_manual_sync_conflict(
        record_id=record_id,
        imported_ip_address=str(imported.get("ip_address") or ""),
        username=username,
    )
    if result == "record_not_found":
        return {"error": "Record not found"}, 404
    if result == "no_conflict":
        return {"error": "Record does not have a resolvable sync conflict."}, 409

    updated = records_repository.fetch_record_by_id(record_id)
    if not updated:
        return {"error": "Record not found"}, 404
    return {"status": "success", "record": updated}, 200
