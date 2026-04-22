import logging
from typing import Any, Dict, Tuple

from app.repositories.scan_events_repository import (
    VALID_EVENT_TYPES,
    insert_scan_event,
)

logger = logging.getLogger(__name__)


def append_scan_event_payload(
    record_id: int,
    event_type: str,
    event_payload: Any,
) -> Tuple[Dict[str, Any], int]:
    if event_type not in VALID_EVENT_TYPES:
        return {"error": f"event_type must be one of: {sorted(VALID_EVENT_TYPES)}"}, 400
    if not isinstance(event_payload, dict):
        event_payload = {}
    try:
        event_id = insert_scan_event(record_id, event_type, event_payload)
        return {"id": event_id}, 201
    except Exception as exc:
        logger.error(f"Failed to insert scan event for record {record_id}: {exc}")
        return {"error": "Failed to store scan event."}, 500


__all__ = ["append_scan_event_payload"]
