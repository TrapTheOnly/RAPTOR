import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.repositories.service_api_repository import (
    PENTEST_WRITABLE_FIELDS,
    VALID_SCAN_STATUSES,
    append_pentest_vulnerability,
    fetch_checklist_templates_dataset,
    fetch_pentests_dataset,
    fetch_records_dataset,
    fetch_single_pentest_dataset,
    get_service_account_key_by_fingerprint,
    touch_service_api_key_last_used,
    update_pentest_fields,
)

logger = logging.getLogger(__name__)

MIN_API_KEY_LENGTH = 24
MAX_API_KEY_LENGTH = 256


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso_datetime(raw_value: Any) -> Optional[datetime]:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def authenticate_service_api_key(api_key: str, required_scope: str) -> Tuple[Dict[str, Any], int]:
    normalized_key = str(api_key or "").strip()
    if not normalized_key:
        return {"error": "API key required."}, 401
    if len(normalized_key) < MIN_API_KEY_LENGTH or len(normalized_key) > MAX_API_KEY_LENGTH:
        return {"error": "Invalid API key."}, 401

    fingerprint = hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()
    try:
        row = get_service_account_key_by_fingerprint(fingerprint)
    except Exception as exc:
        logger.error(f"Error looking up service API key: {exc}")
        return {"error": "Unauthorized access."}, 401

    if not row:
        return {"error": "Unauthorized access."}, 401
    stored_key = str(row.get("api_key") or "")
    if not stored_key or not secrets.compare_digest(stored_key, normalized_key):
        return {"error": "Unauthorized access."}, 401

    expires_at = _parse_iso_datetime(row.get("expires_at"))
    now_utc = _utc_now()
    if not expires_at or expires_at <= now_utc:
        return {"error": "API key expired. Rotate the key."}, 401

    scopes = row.get("scopes") or []
    if required_scope not in scopes:
        return {"error": "API key does not grant this scope."}, 403

    try:
        touch_service_api_key_last_used(int(row.get("key_id")), _isoformat(now_utc))
    except Exception as exc:
        logger.warning(f"Failed to update API key last_used timestamp: {exc}")

    return {
        "service_account": {
            "id": row.get("service_account_id"),
            "username": row.get("username"),
            "scopes": scopes,
        }
    }, 200


def get_service_records_payload() -> Tuple[Dict[str, Any], int]:
    try:
        rows = fetch_records_dataset()
        return {
            "count": len(rows),
            "generated_at": _isoformat(_utc_now()),
            "records": rows,
        }, 200
    except Exception as exc:
        logger.error(f"Failed to fetch service records dataset: {exc}")
        return {"error": "Failed to fetch records dataset."}, 500


def get_service_pentests_payload() -> Tuple[Dict[str, Any], int]:
    try:
        rows = fetch_pentests_dataset()
        return {
            "count": len(rows),
            "generated_at": _isoformat(_utc_now()),
            "pentests": rows,
        }, 200
    except Exception as exc:
        logger.error(f"Failed to fetch service pentests dataset: {exc}")
        return {"error": "Failed to fetch pentests dataset."}, 500


def patch_pentest_payload(record_id: int, fields: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    unknown = [k for k in fields if k not in PENTEST_WRITABLE_FIELDS]
    if unknown:
        return {"error": f"Unknown or non-writable fields: {unknown}"}, 400
    try:
        found = update_pentest_fields(record_id, fields)
    except Exception as exc:
        logger.error(f"Failed to patch pentest {record_id}: {exc}")
        return {"error": "Failed to update pentest."}, 500
    if not found:
        return {"error": "Pentest record not found."}, 404
    return {"message": "Pentest updated."}, 200


def get_single_pentest_payload(record_id: int) -> Tuple[Dict[str, Any], int]:
    try:
        row = fetch_single_pentest_dataset(record_id)
    except Exception as exc:
        logger.error(f"Failed to fetch pentest {record_id}: {exc}")
        return {"error": "Failed to fetch pentest."}, 500
    if not row:
        return {"error": "Pentest record not found."}, 404
    return {"pentest": row}, 200


def set_scan_status_payload(record_id: int, scan_status: str) -> Tuple[Dict[str, Any], int]:
    if scan_status not in VALID_SCAN_STATUSES:
        return {"error": f"scan_status must be one of: {sorted(VALID_SCAN_STATUSES)}"}, 400
    try:
        found = update_pentest_fields(record_id, {"scan_status": scan_status})
    except Exception as exc:
        logger.error(f"Failed to set scan_status for pentest {record_id}: {exc}")
        return {"error": "Failed to update scan status."}, 500
    if not found:
        return {"error": "Pentest record not found."}, 404
    return {"message": "Scan status updated."}, 200


def append_vulnerability_payload(
    record_id: int, vulnerability: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    try:
        found = append_pentest_vulnerability(record_id, vulnerability)
    except Exception as exc:
        logger.error(f"Failed to append vulnerability for pentest {record_id}: {exc}")
        return {"error": "Failed to append vulnerability."}, 500
    if not found:
        return {"error": "Pentest record not found."}, 404
    return {"message": "Vulnerability appended."}, 200


def get_checklist_templates_payload() -> Tuple[Dict[str, Any], int]:
    try:
        rows = fetch_checklist_templates_dataset()
        return {"count": len(rows), "templates": rows}, 200
    except Exception as exc:
        logger.error(f"Failed to fetch checklist templates: {exc}")
        return {"error": "Failed to fetch checklist templates."}, 500


def notify_scan_complete_payload(
    record_id: int,
    findings_count: int,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> Tuple[Dict[str, Any], int]:
    try:
        from app.repositories.offsec.offsec_records import get_pentest_data_internal
        from app.services.notifications_service import notify, _get_usernames_by_roles

        pentest = get_pentest_data_internal(record_id)
        if not pentest:
            return {"error": "Pentest record not found."}, 404

        recipients = list({r for r in [pentest.get("tested_by")] if r})
        recipients += _get_usernames_by_roles(["manager", "admin"])
        message = (
            f"Automated scan completed for {pentest.get('dns_name', f'record {record_id}')}. "
            f"Findings: {findings_count}. "
            f"Tokens: {input_tokens} in / {output_tokens} out. "
            f"Estimated cost: ${cost_usd:.4f}."
        )
        notify(
            notification_type="scan_completed",
            recipients=recipients,
            title="RAPTOR scan completed",
            message=message,
            actor="RAPTOR-Scanner",
            metadata={"record_id": record_id, "findings_count": findings_count},
            send_email_flag=True,
        )
        return {"message": "Notifications sent."}, 200
    except Exception as exc:
        logger.error(f"Failed to send scan-complete notification for record {record_id}: {exc}")
        return {"error": "Failed to send notifications."}, 500


__all__ = [
    "append_vulnerability_payload",
    "authenticate_service_api_key",
    "get_checklist_templates_payload",
    "get_service_pentests_payload",
    "get_service_records_payload",
    "get_single_pentest_payload",
    "notify_scan_complete_payload",
    "patch_pentest_payload",
    "set_scan_status_payload",
]
