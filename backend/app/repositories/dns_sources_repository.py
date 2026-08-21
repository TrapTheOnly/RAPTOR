import json
from typing import Any, Dict, List, Optional, Set

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.services.ingest.secrets import (
    decrypt_config,
    mask_config,
    merge_config,
    parse_source_config,
)

BIND_AGENT_SOURCE_TYPE = "bind_agent"
PULL_SOURCE_TYPES = ("cloudflare", "route53", "alidns", "azure", "gcp")
CLOUD_SOURCE_TYPES = ("cloudflare", "route53", "alidns", "azure", "gcp")


def _row_config(row: Dict[str, Any], *, decrypt: bool = False, mask: bool = False) -> Dict[str, Any]:
    config = parse_source_config(row.get("config"))
    if decrypt:
        config = decrypt_config(config)
    elif mask:
        config = mask_config(decrypt_config(config))
    return config


def _serialize_source(row: Dict[str, Any], *, decrypt: bool = False, mask: bool = True) -> Dict[str, Any]:
    payload = dict(row)
    payload["config"] = _row_config(row, decrypt=decrypt, mask=mask)
    payload["enabled"] = bool(int(row.get("enabled") or 0))
    return payload


def create_dns_source(
    *,
    key: str,
    source_type: str,
    display_name: str,
    config: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH,
) -> int:
    stored_config = json.dumps(merge_config({}, config or {}))
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO dns_sources (key, type, display_name, config, enabled)
            VALUES (?, ?, ?, ?, 1)
            RETURNING id
            """,
            (key, source_type, display_name, stored_config),
        )
        inserted = c.fetchone()
        conn.commit()
    return int(inserted["id"] if isinstance(inserted, dict) else inserted[0])


def get_dns_source(
    source_id: int,
    db_path: str = DB_PATH,
    *,
    decrypt: bool = False,
    mask: bool = True,
) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT * FROM dns_sources WHERE id = ?", (source_id,))
        row = c.fetchone()
    if not row:
        return None
    return _serialize_source(dict(row), decrypt=decrypt, mask=mask and not decrypt)


def list_dns_sources(
    *,
    types: Optional[List[str]] = None,
    enabled_only: bool = False,
    db_path: str = DB_PATH,
    decrypt: bool = False,
    mask: bool = True,
) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if types:
        placeholders = ",".join("?" for _ in types)
        clauses.append(f"type IN ({placeholders})")
        params.extend(types)
    if enabled_only:
        clauses.append("enabled = 1")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(f"SELECT * FROM dns_sources {where} ORDER BY type, display_name, id", tuple(params))
        rows = c.fetchall() or []
    return [
        _serialize_source(dict(row), decrypt=decrypt, mask=mask and not decrypt)
        for row in rows
    ]


def update_dns_source(
    source_id: int,
    *,
    display_name: Optional[str] = None,
    enabled: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    existing = get_dns_source(source_id, db_path=db_path, decrypt=True, mask=False)
    if not existing:
        return None
    next_name = display_name if display_name is not None else existing.get("display_name")
    next_enabled = existing.get("enabled") if enabled is None else bool(enabled)
    next_config = merge_config(existing.get("config") or {}, config if config is not None else {})
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE dns_sources
            SET display_name = ?, enabled = ?, config = ?
            WHERE id = ?
            """,
            (next_name, 1 if next_enabled else 0, json.dumps(next_config), source_id),
        )
        conn.commit()
    return get_dns_source(source_id, db_path=db_path, mask=True)


def disable_dns_source(source_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("UPDATE dns_sources SET enabled = 0 WHERE id = ?", (source_id,))
        updated = c.rowcount
        conn.commit()
    return bool(updated)


def delete_dns_source(source_id: int, db_path: str = DB_PATH) -> bool:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM dns_sources WHERE id = ?", (source_id,))
        deleted = c.rowcount
        conn.commit()
    return bool(deleted)


def record_observations(
    source_id: int,
    records: List[Dict[str, Any]],
    batch_id: str,
    db_path: str = DB_PATH,
    cursor_value: Optional[str] = None,
) -> None:
    if not records:
        return
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        for record in records:
            fqdn = record.get("fqdn") or record.get("name")
            rrtype = str(record.get("rrtype") or "A").upper()
            rdata = record.get("rdata")
            if rdata is None:
                rdata = record.get("ip_address")
            ttl = record.get("ttl")
            c.execute(
                """
                INSERT INTO dns_observations (
                    source_id, fqdn, rrtype, rdata, ttl, observed_at, batch_id,
                    provider_zone_id, provider_record_id, zone
                )
                VALUES (?, ?, ?, ?, ?, NOW(), ?, ?, ?, ?)
                """,
                (
                    source_id,
                    fqdn,
                    rrtype,
                    rdata,
                    ttl,
                    batch_id,
                    record.get("provider_zone_id") or None,
                    record.get("provider_record_id") or None,
                    record.get("zone") or None,
                ),
            )
        c.execute(
            """
            UPDATE dns_sources
            SET last_success_at = NOW(), last_error = NULL, cursor = ?
            WHERE id = ?
            """,
            (cursor_value or batch_id, source_id),
        )
        conn.commit()


def previously_observed_names(source_id: int, db_path: str = DB_PATH) -> List[str]:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT DISTINCT fqdn FROM dns_observations WHERE source_id = ? AND rrtype = 'A'",
            (source_id,),
        )
        rows = c.fetchall()
    names = []
    for row in rows:
        if isinstance(row, dict):
            names.append(str(row["fqdn"]))
        else:
            names.append(str(row[0]))
    return names


def latest_live_a_fqdns(db_path: str = DB_PATH) -> Set[str]:
    """A names present in the latest batch of any enabled source."""
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            WITH latest_batch AS (
                SELECT DISTINCT ON (o.source_id) o.source_id, o.batch_id
                FROM dns_observations o
                JOIN dns_sources s ON s.id = o.source_id
                WHERE s.enabled = 1 AND o.batch_id IS NOT NULL AND o.batch_id <> ''
                ORDER BY o.source_id, o.observed_at DESC, o.id DESC
            )
            SELECT DISTINCT o.fqdn
            FROM dns_observations o
            JOIN latest_batch b ON b.source_id = o.source_id AND b.batch_id = o.batch_id
            WHERE o.rrtype = 'A'
            """
        )
        rows = c.fetchall() or []
    names: Set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            names.add(str(row.get("fqdn") or ""))
        else:
            names.add(str(row[0] or ""))
    names.discard("")
    return names


def latest_a_observations_for_fqdn(fqdn: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    name = str(fqdn or "").strip().lower().rstrip(".")
    if not name:
        return []
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            WITH latest_batch AS (
                SELECT DISTINCT ON (o.source_id) o.source_id, o.batch_id
                FROM dns_observations o
                JOIN dns_sources s ON s.id = o.source_id
                WHERE s.enabled = 1 AND o.batch_id IS NOT NULL AND o.batch_id <> ''
                ORDER BY o.source_id, o.observed_at DESC, o.id DESC
            )
            SELECT
                s.id AS source_id,
                s.key AS source_key,
                s.type AS source_type,
                s.display_name,
                o.rdata AS ip_address,
                o.zone,
                o.provider_zone_id,
                o.observed_at
            FROM dns_observations o
            JOIN latest_batch b ON b.source_id = o.source_id AND b.batch_id = o.batch_id
            JOIN dns_sources s ON s.id = o.source_id
            WHERE o.rrtype = 'A' AND o.fqdn = ?
            ORDER BY s.display_name, s.id
            """,
            (name,),
        )
        rows = c.fetchall() or []
    seen = []
    for row in rows:
        item = dict(row)
        item["source_id"] = int(item.get("source_id") or 0)
        seen.append(item)
    return seen


def list_zones_for_source(source_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            WITH latest_batch AS (
                SELECT batch_id
                FROM dns_observations
                WHERE source_id = ? AND batch_id IS NOT NULL AND batch_id <> ''
                ORDER BY observed_at DESC, id DESC
                LIMIT 1
            )
            SELECT
                COALESCE(NULLIF(o.zone, ''), o.provider_zone_id, '') AS zone,
                o.provider_zone_id,
                COUNT(*) AS record_count
            FROM dns_observations o
            JOIN latest_batch b ON b.batch_id = o.batch_id
            WHERE o.source_id = ?
            GROUP BY 1, 2
            ORDER BY 1
            """,
            (source_id, source_id),
        )
        rows = c.fetchall() or []
    return [dict(row) for row in rows if str(row.get("zone") or "").strip()]


def mark_source_error(source_id: int, error: str, db_path: str = DB_PATH) -> None:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE dns_sources SET last_error = ? WHERE id = ?",
            (error[:2000], source_id),
        )
        conn.commit()


__all__ = [
    "BIND_AGENT_SOURCE_TYPE",
    "CLOUD_SOURCE_TYPES",
    "PULL_SOURCE_TYPES",
    "create_dns_source",
    "delete_dns_source",
    "disable_dns_source",
    "get_dns_source",
    "latest_a_observations_for_fqdn",
    "latest_live_a_fqdns",
    "list_dns_sources",
    "list_zones_for_source",
    "mark_source_error",
    "previously_observed_names",
    "record_observations",
    "update_dns_source",
]
