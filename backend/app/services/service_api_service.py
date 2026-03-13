import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.repositories.service_api_repository import (
    fetch_pentests_dataset,
    fetch_records_dataset,
    get_service_account_key_by_fingerprint,
    touch_service_api_key_last_used,
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


__all__ = [
    "authenticate_service_api_key",
    "get_service_pentests_payload",
    "get_service_records_payload",
]
