import logging
from typing import Any, Dict, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

logger = logging.getLogger(__name__)


def record_audit_event(
    *,
    actor: str,
    actor_type: str,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH,
) -> None:
    import json

    try:
        with get_db_connection(db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO audit_events (at, actor, actor_type, action, entity_type, entity_id, metadata)
                VALUES (NOW(), ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(actor or "")[:128],
                    str(actor_type or "user")[:32],
                    str(action or "")[:128],
                    str(entity_type or "")[:64],
                    str(entity_id or "")[:128],
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to write audit event %s: %s", action, exc)


__all__ = ["record_audit_event"]
