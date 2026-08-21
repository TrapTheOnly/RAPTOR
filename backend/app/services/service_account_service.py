import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.service_api_repository import (
    IntegrityError,
    SERVICE_API_SCOPES,
    create_service_account_key,
    get_service_account_by_username,
    get_service_account_with_key,
    list_service_accounts,
    rotate_service_account_key,
    update_service_account_keycloak_client,
    update_service_account_scopes,
)

logger = logging.getLogger(__name__)

DEFAULT_KEY_ROTATION_DAYS = 90
MIN_KEY_LENGTH = 24
MAX_KEY_LENGTH = 256
USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,64}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_username(raw_username: Any) -> str:
    return str(raw_username or "").strip().lower()


def _parse_end_date(raw_value: Any) -> Optional[datetime]:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        if len(value) == 10 and value.count("-") == 2:
            parsed = datetime.fromisoformat(value + "T23:59:59+00:00")
        else:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0)
    except ValueError:
        return None


def _sanitize_scopes(raw_scopes: Any) -> Optional[List[str]]:
    if not isinstance(raw_scopes, list):
        return None
    deduped = []
    for scope in raw_scopes:
        normalized = str(scope or "").strip().lower()
        if normalized in SERVICE_API_SCOPES and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _generate_api_key() -> str:
    token = secrets.token_urlsafe(48)
    if len(token) < MIN_KEY_LENGTH:
        token = token + secrets.token_urlsafe(24)
    return f"raptor_sk_{token}"[:MAX_KEY_LENGTH]


def _fingerprint_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _build_service_account_payload(
    row: Dict[str, Any],
    include_key: bool = False,
) -> Dict[str, Any]:
    payload = {
        "service_account_id": row.get("service_account_id"),
        "username": row.get("username"),
        "added_date": row.get("added_date"),
        "has_api_key": bool(row.get("has_api_key")),
        "scopes": row.get("scopes") or [],
        "key_created_at": row.get("key_created_at"),
        "expires_at": row.get("expires_at"),
        "rotated_at": row.get("rotated_at"),
        "last_used_at": row.get("last_used_at"),
        "created_by": row.get("created_by"),
        "rotated_by": row.get("rotated_by"),
    }
    if include_key and row.get("api_key"):
        payload["api_key"] = row.get("api_key")
    return payload


def get_service_accounts_service() -> Tuple[Dict[str, Any], int]:
    try:
        rows = list_service_accounts()
        payload = [_build_service_account_payload(row, include_key=False) for row in rows]
        return {"service_accounts": payload}, 200
    except Exception as exc:
        logger.error(f"Error listing service accounts: {exc}")
        return {"error": "Failed to list service accounts."}, 500


def create_service_account_service(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = _normalize_username(data.get("username"))
    if not username:
        return {"error": "Username is required."}, 400
    if not USERNAME_PATTERN.match(username):
        return {"error": "Username must be 3-64 chars and contain only a-z, 0-9, ., _, -."}, 400

    try:
        from app.services.keycloak_identity_service import provision_service_account

        provision_service_account(username)
        row = get_service_account_by_username(username)
        if not row:
            return {"error": "Service account created but could not be loaded."}, 500
        return {
            "message": f"Service account {username} created successfully.",
            "service_account": _build_service_account_payload(dict(row), include_key=False),
        }, 201
    except ValueError:
        return {"error": "Service account username already exists."}, 409
    except IntegrityError:
        return {"error": "Service account username already exists."}, 409
    except Exception as exc:
        logger.error(f"Error creating service account {username}: {exc}")
        return {"error": "Failed to create service account."}, 500


def create_service_account_key_service(
    username: str,
    data: Dict[str, Any],
    actor_username: str,
) -> Tuple[Dict[str, Any], int]:
    normalized_username = _normalize_username(username)
    row = get_service_account_with_key(normalized_username)
    if not row:
        return {"error": "Service account not found."}, 404
    if row.get("has_api_key"):
        return {"error": "API key already exists. Use rotation."}, 409

    scopes = _sanitize_scopes(data.get("scopes", []))
    if scopes is None:
        return {"error": "Scopes must be a list."}, 400
    if not scopes:
        return {"error": "At least one scope is required."}, 400

    custom_end = _parse_end_date(data.get("end_date"))
    if data.get("end_date") and custom_end is None:
        return {"error": "Invalid end_date. Use ISO datetime or YYYY-MM-DD."}, 400

    now_utc = _utc_now()
    expires_at = custom_end or (now_utc + timedelta(days=DEFAULT_KEY_ROTATION_DAYS))
    if expires_at <= now_utc:
        return {"error": "end_date must be in the future."}, 400

    api_key = _generate_api_key()
    api_key_fingerprint = _fingerprint_key(api_key)
    scopes_json = json.dumps(scopes)

    try:
        from app.services.keycloak_identity_service import push_service_account_credentials

        client_uuid = push_service_account_credentials(
            normalized_username,
            api_key,
            scopes,
            _isoformat(expires_at),
        )
        update_service_account_keycloak_client(normalized_username, client_uuid)
        create_service_account_key(
            service_account_id=int(row["service_account_id"]),
            api_key=api_key,
            api_key_fingerprint=api_key_fingerprint,
            scopes_json=scopes_json,
            created_at=_isoformat(now_utc),
            expires_at=_isoformat(expires_at),
            actor_username=_normalize_username(actor_username),
        )
        refreshed = get_service_account_with_key(normalized_username)
        if not refreshed:
            return {"error": "API key created but could not be loaded."}, 500
        payload = _build_service_account_payload(refreshed, include_key=False)
        payload["api_key"] = api_key
        from app.services.audit_service import record_audit_event

        record_audit_event(
            actor=_normalize_username(actor_username),
            actor_type="user",
            action="api_key.create",
            entity_type="service_account",
            entity_id=normalized_username,
            metadata={},
        )
        return {
            "message": "API key created successfully.",
            "service_account": payload,
        }, 201
    except IntegrityError:
        return {"error": "API key collision detected. Retry creation."}, 409
    except Exception as exc:
        logger.error(f"Error creating API key for service account {normalized_username}: {exc}")
        return {"error": "Failed to create API key."}, 500


def view_service_account_key_service(username: str) -> Tuple[Dict[str, Any], int]:
    normalized_username = _normalize_username(username)
    row = get_service_account_with_key(normalized_username)
    if not row:
        return {"error": "Service account not found."}, 404
    if not row.get("has_api_key"):
        return {"error": "API key not created yet."}, 404
    return {
        "error": "API keys cannot be viewed after creation. Rotate to issue a new key.",
    }, 410


def rotate_service_account_key_service(
    username: str,
    actor_username: str,
) -> Tuple[Dict[str, Any], int]:
    normalized_username = _normalize_username(username)
    row = get_service_account_with_key(normalized_username)
    if not row:
        return {"error": "Service account not found."}, 404
    if not row.get("has_api_key"):
        return {"error": "API key not created yet."}, 404

    scopes = row.get("scopes") or []
    if not scopes:
        return {"error": "Service account must have at least one scope before rotation."}, 400

    now_utc = _utc_now()
    expires_at = now_utc + timedelta(days=DEFAULT_KEY_ROTATION_DAYS)
    api_key = _generate_api_key()
    api_key_fingerprint = _fingerprint_key(api_key)

    try:
        from app.services.keycloak_identity_service import push_service_account_credentials

        push_service_account_credentials(
            normalized_username,
            api_key,
            scopes,
            _isoformat(expires_at),
        )
        updated = rotate_service_account_key(
            service_account_id=int(row["service_account_id"]),
            api_key=api_key,
            api_key_fingerprint=api_key_fingerprint,
            scopes_json=json.dumps(scopes),
            rotated_at=_isoformat(now_utc),
            expires_at=_isoformat(expires_at),
            actor_username=_normalize_username(actor_username),
        )
        if updated == 0:
            return {"error": "API key not found for service account."}, 404
        refreshed = get_service_account_with_key(normalized_username)
        if not refreshed:
            return {"error": "API key rotated but could not be loaded."}, 500
        payload = _build_service_account_payload(refreshed, include_key=False)
        payload["api_key"] = api_key
        from app.services.audit_service import record_audit_event

        record_audit_event(
            actor=_normalize_username(actor_username),
            actor_type="user",
            action="api_key.rotate",
            entity_type="service_account",
            entity_id=normalized_username,
            metadata={},
        )
        return {
            "message": "API key rotated successfully.",
            "service_account": payload,
        }, 200
    except IntegrityError:
        return {"error": "API key collision detected. Retry rotation."}, 409
    except Exception as exc:
        logger.error(f"Error rotating API key for service account {normalized_username}: {exc}")
        return {"error": "Failed to rotate API key."}, 500


def update_service_account_scopes_service(
    username: str,
    data: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    normalized_username = _normalize_username(username)
    row = get_service_account_with_key(normalized_username)
    if not row:
        return {"error": "Service account not found."}, 404
    if not row.get("has_api_key"):
        return {"error": "API key not created yet."}, 404

    scopes = _sanitize_scopes(data.get("scopes", []))
    if scopes is None:
        return {"error": "Scopes must be a list."}, 400
    if not scopes:
        return {"error": "At least one scope is required."}, 400

    try:
        from app.services.keycloak_identity_service import apply_service_account_scopes

        apply_service_account_scopes(normalized_username, scopes)
        updated = update_service_account_scopes(int(row["service_account_id"]), json.dumps(scopes))
        if updated == 0:
            return {"error": "Service account API key not found."}, 404
        refreshed = get_service_account_with_key(normalized_username)
        if not refreshed:
            return {"error": "Scopes updated but service account could not be loaded."}, 500
        return {
            "message": "Service account scopes updated.",
            "service_account": _build_service_account_payload(refreshed, include_key=False),
        }, 200
    except Exception as exc:
        logger.error(f"Error updating scopes for service account {normalized_username}: {exc}")
        return {"error": "Failed to update service account scopes."}, 500


__all__ = [
    "DEFAULT_KEY_ROTATION_DAYS",
    "create_service_account_key_service",
    "create_service_account_service",
    "get_service_accounts_service",
    "rotate_service_account_key_service",
    "update_service_account_scopes_service",
    "view_service_account_key_service",
]
