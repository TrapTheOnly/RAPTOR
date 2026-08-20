import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.services.llm.recipes import (
    LOCAL_DISPLAY_NAME,
    LOCAL_TYPE,
    default_local_models,
    secret_fields_for,
)
from app.services.llm.secrets import (
    decrypt_config,
    mask_config,
    merge_config,
    parse_source_config,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_models(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    if isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(loaded, list):
            return [dict(item) for item in loaded if isinstance(item, dict)]
    return []


def _serialize(
    row: Dict[str, Any],
    *,
    decrypt: bool = False,
    mask: bool = True,
) -> Dict[str, Any]:
    kind = str(row.get("type") or "")
    secrets = secret_fields_for(kind)
    config = parse_source_config(row.get("config"))
    if decrypt:
        config = decrypt_config(config, secret_fields=secrets)
    elif mask:
        config = mask_config(decrypt_config(config, secret_fields=secrets), secret_fields=secrets)
    payload = dict(row)
    payload["config"] = config
    payload["models"] = _parse_models(row.get("models"))
    payload["enabled"] = bool(int(row.get("enabled") or 0))
    return payload


def list_connections(
    *,
    db_path: str = DB_PATH,
    decrypt: bool = False,
    mask: bool = True,
) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM llm_connections ORDER BY type = 'local' DESC, display_name, id")
        rows = c.fetchall() or []
    return [_serialize(dict(row), decrypt=decrypt, mask=mask and not decrypt) for row in rows]


def get_connection(
    connection_id: int,
    *,
    db_path: str = DB_PATH,
    decrypt: bool = False,
    mask: bool = True,
) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM llm_connections WHERE id = ?", (connection_id,))
        row = c.fetchone()
    if not row:
        return None
    return _serialize(dict(row), decrypt=decrypt, mask=mask and not decrypt)


def get_local_connection(
    *,
    db_path: str = DB_PATH,
    decrypt: bool = False,
    mask: bool = True,
) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM llm_connections WHERE type = ? ORDER BY id ASC LIMIT 1", (LOCAL_TYPE,))
        row = c.fetchone()
    if not row:
        return None
    return _serialize(dict(row), decrypt=decrypt, mask=mask and not decrypt)


def create_connection(
    *,
    provider_type: str,
    display_name: str,
    config: Optional[Dict[str, Any]] = None,
    models: Optional[List[Dict[str, Any]]] = None,
    enabled: bool = True,
    db_path: str = DB_PATH,
) -> int:
    secrets = secret_fields_for(provider_type)
    stored_config = json.dumps(merge_config({}, config or {}, secret_fields=secrets))
    stored_models = json.dumps(models or [])
    now = _utc_now()
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO llm_connections (type, display_name, config, models, enabled, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                provider_type,
                display_name,
                stored_config,
                stored_models,
                1 if enabled else 0,
                now,
            ),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def update_connection(
    connection_id: int,
    *,
    display_name: Optional[str] = None,
    enabled: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None,
    models: Optional[List[Dict[str, Any]]] = None,
    last_error: Optional[str] = None,
    last_checked_at: Optional[str] = None,
    updated_by: Optional[str] = None,
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    existing = get_connection(connection_id, db_path=db_path, decrypt=True, mask=False)
    if not existing:
        return None
    secrets = secret_fields_for(str(existing.get("type")))
    fields: Dict[str, Any] = {"updated_at": _utc_now()}
    if display_name is not None:
        fields["display_name"] = str(display_name).strip()
    if enabled is not None:
        fields["enabled"] = 1 if enabled else 0
    if config is not None:
        fields["config"] = json.dumps(
            merge_config(existing.get("config") or {}, config, secret_fields=secrets)
        )
    if models is not None:
        fields["models"] = json.dumps(models)
    if last_error is not None:
        fields["last_error"] = last_error
    if last_checked_at is not None:
        fields["last_checked_at"] = last_checked_at
    if updated_by is not None:
        fields["updated_by"] = updated_by
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [connection_id]
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE llm_connections SET {assignments} WHERE id = ?", values)
        conn.commit()
    return get_connection(connection_id, db_path=db_path, mask=True)


def delete_connection(connection_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM llm_connections WHERE id = ? AND type <> ?", (connection_id, LOCAL_TYPE))
        deleted = c.rowcount
        conn.commit()
    return bool(deleted)


def ensure_local_connection(db_path: str = DB_PATH) -> int:
    existing = get_local_connection(db_path=db_path, mask=False, decrypt=False)
    if existing:
        return int(existing["id"])
    return create_connection(
        provider_type=LOCAL_TYPE,
        display_name=LOCAL_DISPLAY_NAME,
        config={},
        models=default_local_models(),
        enabled=True,
        db_path=db_path,
    )


__all__ = [
    "create_connection",
    "delete_connection",
    "ensure_local_connection",
    "get_connection",
    "get_local_connection",
    "list_connections",
    "update_connection",
]
