from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection


def _json_value(raw: Any, fallback: Any) -> Any:
    if raw is None:
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return fallback
        try:
            return json.loads(text)
        except ValueError:
            return fallback
    return fallback


def _dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=True)


def _row_connection(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "kind": row.get("kind"),
        "name": row.get("name"),
        "base_url": row.get("base_url"),
        "auth_type": row.get("auth_type") or "api_token",
        "auth_email": row.get("auth_email") or "",
        "secret_ciphertext": row.get("secret_ciphertext") or "",
        "extra": _json_value(row.get("extra_json"), {}),
        "status": row.get("status") or "draft",
        "last_error": row.get("last_error") or "",
        "created_by": row.get("created_by") or "",
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def _row_template(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "connection_id": row.get("connection_id"),
        "name": row.get("name"),
        "external_project_key": row.get("external_project_key") or "",
        "external_project_name": row.get("external_project_name") or "",
        "issue_type_id": row.get("issue_type_id") or "",
        "issue_type_name": row.get("issue_type_name") or "",
        "extra": _json_value(row.get("extra_json"), {}),
        "is_default": bool(row.get("is_default")),
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def _row_mapping(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "template_id": row.get("template_id"),
        "raptor_field": row.get("raptor_field") or "",
        "external_field_id": row.get("external_field_id"),
        "external_field_name": row.get("external_field_name") or "",
        "external_field_type": row.get("external_field_type") or "string",
        "fill_mode": row.get("fill_mode") or "ask",
        "static_value": row.get("static_value") or "",
        "required": bool(row.get("required")),
        "allowed_values": _json_value(row.get("allowed_values_json"), []),
        "sort_order": int(row.get("sort_order") or 0),
    }


def _row_export(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "connection_id": row.get("connection_id"),
        "template_id": row.get("template_id"),
        "kind": row.get("kind"),
        "scope": row.get("scope"),
        "finding_id": str(row.get("finding_id") or ""),
        "wave_id": row.get("wave_id"),
        "application_id": row.get("application_id"),
        "external_id": row.get("external_id") or "",
        "external_url": row.get("external_url") or "",
        "payload": _json_value(row.get("payload_json"), {}),
        "status": row.get("status"),
        "error": row.get("error") or "",
        "created_by": row.get("created_by") or "",
        "created_at": str(row.get("created_at") or ""),
    }


def list_connections(kind: Optional[str] = None, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        cursor = conn.cursor()
        if kind:
            cursor.execute(
                "SELECT * FROM integration_connections WHERE kind = ? ORDER BY id",
                (kind,),
            )
        else:
            cursor.execute("SELECT * FROM integration_connections ORDER BY kind, id")
        return [_row_connection(dict(row)) for row in cursor.fetchall()]


def get_connection(connection_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM integration_connections WHERE id = ?", (connection_id,))
        row = cursor.fetchone()
        return _row_connection(dict(row)) if row else None


def insert_connection(data: Dict[str, Any], db_path: str = DB_PATH) -> Dict[str, Any]:
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO integration_connections (
                kind, name, base_url, auth_type, auth_email, secret_ciphertext,
                extra_json, status, last_error, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?::jsonb, ?, ?, ?)
            RETURNING id
            """,
            (
                data["kind"],
                data["name"],
                data["base_url"],
                data.get("auth_type") or "api_token",
                data.get("auth_email") or "",
                data.get("secret_ciphertext") or "",
                _dump(data.get("extra") or {}),
                data.get("status") or "draft",
                data.get("last_error") or "",
                data.get("created_by") or "",
            ),
        )
        row = cursor.fetchone()
        connection_id = row[0] if not isinstance(row, dict) else row["id"]
        conn.commit()
    result = get_connection(int(connection_id), db_path=db_path)
    if not result:
        raise RuntimeError("Failed to load created integration connection.")
    return result


def update_connection(connection_id: int, fields: Dict[str, Any], db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    allowed = {
        "name": "name",
        "base_url": "base_url",
        "auth_type": "auth_type",
        "auth_email": "auth_email",
        "secret_ciphertext": "secret_ciphertext",
        "status": "status",
        "last_error": "last_error",
    }
    assignments = []
    values: List[Any] = []
    for key, column in allowed.items():
        if key in fields:
            assignments.append(f"{column} = ?")
            values.append(fields[key])
    if "extra" in fields:
        assignments.append("extra_json = ?::jsonb")
        values.append(_dump(fields.get("extra") or {}))
    if not assignments:
        return get_connection(connection_id, db_path=db_path)
    values.append(connection_id)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE integration_connections SET {', '.join(assignments)}, updated_at = NOW() WHERE id = ?",
            tuple(values),
        )
        conn.commit()
    return get_connection(connection_id, db_path=db_path)


def delete_connection(connection_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM integration_connections WHERE id = ?", (connection_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
    return deleted


def list_templates(connection_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM integration_templates
            WHERE connection_id = ?
            ORDER BY is_default DESC, id
            """,
            (connection_id,),
        )
        return [_row_template(dict(row)) for row in cursor.fetchall()]


def get_template(template_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM integration_templates WHERE id = ?", (template_id,))
        row = cursor.fetchone()
        return _row_template(dict(row)) if row else None


def insert_template(data: Dict[str, Any], db_path: str = DB_PATH) -> Dict[str, Any]:
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if data.get("is_default"):
            cursor.execute(
                "UPDATE integration_templates SET is_default = FALSE WHERE connection_id = ?",
                (data["connection_id"],),
            )
        cursor.execute(
            """
            INSERT INTO integration_templates (
                connection_id, name, external_project_key, external_project_name,
                issue_type_id, issue_type_name, extra_json, is_default
            )
            VALUES (?, ?, ?, ?, ?, ?, ?::jsonb, ?)
            RETURNING id
            """,
            (
                data["connection_id"],
                data["name"],
                data.get("external_project_key") or "",
                data.get("external_project_name") or "",
                data.get("issue_type_id") or "",
                data.get("issue_type_name") or "",
                _dump(data.get("extra") or {}),
                bool(data.get("is_default")),
            ),
        )
        row = cursor.fetchone()
        template_id = row[0] if not isinstance(row, dict) else row["id"]
        conn.commit()
    result = get_template(int(template_id), db_path=db_path)
    if not result:
        raise RuntimeError("Failed to load created integration template.")
    return result


def update_template(template_id: int, fields: Dict[str, Any], db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    current = get_template(template_id, db_path=db_path)
    if not current:
        return None
    allowed = {
        "name": "name",
        "external_project_key": "external_project_key",
        "external_project_name": "external_project_name",
        "issue_type_id": "issue_type_id",
        "issue_type_name": "issue_type_name",
        "is_default": "is_default",
    }
    assignments = []
    values: List[Any] = []
    for key, column in allowed.items():
        if key in fields:
            assignments.append(f"{column} = ?")
            values.append(fields[key])
    if "extra" in fields:
        assignments.append("extra_json = ?::jsonb")
        values.append(_dump(fields.get("extra") or {}))
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if fields.get("is_default"):
            cursor.execute(
                "UPDATE integration_templates SET is_default = FALSE WHERE connection_id = ? AND id <> ?",
                (current["connection_id"], template_id),
            )
        if assignments:
            values.append(template_id)
            cursor.execute(
                f"UPDATE integration_templates SET {', '.join(assignments)}, updated_at = NOW() WHERE id = ?",
                tuple(values),
            )
        conn.commit()
    return get_template(template_id, db_path=db_path)


def delete_template(template_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM integration_templates WHERE id = ?", (template_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
    return deleted


def list_mappings(template_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM integration_field_maps
            WHERE template_id = ?
            ORDER BY sort_order, id
            """,
            (template_id,),
        )
        return [_row_mapping(dict(row)) for row in cursor.fetchall()]


def replace_mappings(template_id: int, mappings: List[Dict[str, Any]], db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM integration_field_maps WHERE template_id = ?", (template_id,))
        for index, item in enumerate(mappings or []):
            cursor.execute(
                """
                INSERT INTO integration_field_maps (
                    template_id, raptor_field, external_field_id, external_field_name,
                    external_field_type, fill_mode, static_value, required,
                    allowed_values_json, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?)
                """,
                (
                    template_id,
                    item.get("raptor_field") or "",
                    item["external_field_id"],
                    item.get("external_field_name") or "",
                    item.get("external_field_type") or "string",
                    item.get("fill_mode") or "ask",
                    item.get("static_value") or "",
                    bool(item.get("required")),
                    json.dumps(item.get("allowed_values") or [], ensure_ascii=True),
                    item.get("sort_order", index),
                ),
            )
        conn.commit()
    return list_mappings(template_id, db_path=db_path)


def list_exports_for_findings(
    finding_ids: Iterable[Any],
    kind: Optional[str] = None,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    ids = [str(item) for item in finding_ids if item not in (None, "")]
    if not ids:
        return []
    placeholders = ", ".join("?" for _ in ids)
    sql = f"""
        SELECT * FROM integration_exports
        WHERE finding_id IN ({placeholders}) AND status = 'created'
    """
    params: List[Any] = list(ids)
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY created_at DESC, id DESC"
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        return [_row_export(dict(row)) for row in cursor.fetchall()]


def latest_export_urls(
    finding_ids: Iterable[Any],
    kind: str,
    db_path: str = DB_PATH,
) -> Dict[str, str]:
    urls: Dict[str, str] = {}
    try:
        rows = list_exports_for_findings(finding_ids, kind=kind, db_path=db_path)
    except Exception:
        return urls
    for row in rows:
        finding_id = str(row.get("finding_id") or "")
        if not finding_id or finding_id in urls:
            continue
        url = str(row.get("external_url") or "").strip()
        if url:
            urls[finding_id] = url
    return urls


def insert_export(data: Dict[str, Any], db_path: str = DB_PATH) -> Dict[str, Any]:
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO integration_exports (
                connection_id, template_id, kind, scope, finding_id, wave_id,
                application_id, external_id, external_url, payload_json, status,
                error, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?, ?, ?)
            RETURNING id
            """,
            (
                data.get("connection_id"),
                data.get("template_id"),
                data["kind"],
                data.get("scope") or "finding",
                str(data.get("finding_id") or "") or None,
                data.get("wave_id"),
                data.get("application_id"),
                data.get("external_id") or "",
                data.get("external_url") or "",
                _dump(data.get("payload") or {}),
                data.get("status") or "created",
                data.get("error") or "",
                data.get("created_by") or "",
            ),
        )
        row = cursor.fetchone()
        export_id = row[0] if not isinstance(row, dict) else row["id"]
        conn.commit()
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM integration_exports WHERE id = ?", (export_id,))
        loaded = cursor.fetchone()
    return _row_export(dict(loaded)) if loaded else {"id": export_id}
