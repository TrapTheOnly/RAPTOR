import logging
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import IntegrityError, get_db_connection
from app.repositories.dns_sources_repository import latest_a_observations_for_fqdn, latest_live_a_fqdns
from app.repositories.records_row_mapper import determine_source_with_cursor

logger = logging.getLogger(__name__)

MANUAL_SYNC_CONFLICT_REASON = "manual_domain_matches_import"
MULTI_SOURCE_A_CONFLICT_REASON = "multi_source_a_disagreement"


def _insert_record_history(
    cursor: Any,
    *,
    record_id: int,
    action: str,
    username: str,
    old_ip_address: Optional[str] = None,
    new_ip_address: Optional[str] = None,
    old_source: Optional[str] = None,
    new_source: Optional[str] = None,
    old_maintainer: Optional[str] = None,
    new_maintainer: Optional[str] = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO record_history (record_id, action, timestamp, username,
                                   old_ip_address, new_ip_address,
                                   old_source, new_source,
                                   old_maintainer, new_maintainer)
        VALUES (?, ?, (NOW() + INTERVAL '4 hours'), ?,
                ?, ?,
                ?, ?,
                ?, ?)
        """,
        (
            record_id,
            action,
            username,
            old_ip_address,
            new_ip_address,
            old_source,
            new_source,
            old_maintainer,
            new_maintainer,
        ),
    )


def _create_initial_pentest_row(
    cursor: Any,
    *,
    record_id: int,
    dns_name: str,
    ip_address: str,
    source: str,
    open_ports: str = "",
) -> None:
    cursor.execute(
        """
        INSERT INTO pentest_data (record_id, dns_name, ip_address, source, open_ports)
        VALUES (?, ?, ?, ?, ?)
        """,
        (record_id, dns_name, ip_address, source, open_ports),
    )


def store_records_in_db(
    records: List[Dict[str, Any]],
    db_path: str = DB_PATH,
    source_id: Optional[int] = None,
) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    c.execute("SELECT id, name, ip_address, source, maintainer, origin, sync_conflict FROM records")
    existing_records = {
        row[1]: {
            "id": row[0],
            "ip_address": row[2],
            "source": row[3],
            "maintainer": row[4],
            "origin": row[5],
            "sync_conflict": bool(row[6]),
        }
        for row in c.fetchall()
    }

    current_names = {r["name"] for r in records}

    for record in records:
        if record["name"] in existing_records:
            existing_record = existing_records[record["name"]]

            if existing_record["origin"] == "manual":
                c.execute(
                    """
                    UPDATE records
                    SET sync_conflict = 1,
                        sync_conflict_reason = ?,
                        last_modification_date = (NOW() + INTERVAL '4 hours')
                    WHERE id = ?
                    """,
                    (MANUAL_SYNC_CONFLICT_REASON, existing_record["id"]),
                )
                if not existing_record["sync_conflict"]:
                    _insert_record_history(
                        c,
                        record_id=existing_record["id"],
                        action="conflict",
                        username="system",
                        old_ip_address=existing_record["ip_address"],
                        new_ip_address=record["ip_address"],
                        old_source=existing_record["source"],
                        new_source=record["source"],
                        old_maintainer=existing_record["maintainer"],
                        new_maintainer=existing_record["maintainer"],
                    )
                    try:
                        from app.services.notifications_service import notify_by_roles
                        notify_by_roles(
                            notification_type="sync_conflict",
                            roles=["admin", "manager"],
                            title="Sync conflict detected",
                            message=f"Record '{record['name']}' has a sync conflict requiring resolution.",
                            metadata={"record_id": existing_record["id"]},
                        )
                    except Exception:
                        pass
                continue

            new_source = determine_source_with_cursor(c, record["ip_address"])
            other_ips = {
                str(row.get("ip_address") or "")
                for row in latest_a_observations_for_fqdn(record["name"], db_path=db_path)
                if int(row.get("source_id") or 0) != int(source_id or 0) and row.get("ip_address")
            }
            other_ips.discard("")

            if (
                existing_record["ip_address"] != record["ip_address"]
                and other_ips
                and record["ip_address"] not in other_ips
            ):
                if not existing_record["sync_conflict"]:
                    try:
                        from app.services.notifications_service import notify_by_roles

                        notify_by_roles(
                            notification_type="sync_conflict",
                            roles=["admin", "manager"],
                            title="Sync conflict detected",
                            message=(
                                f"Record '{record['name']}' has A records that disagree across DNS sources."
                            ),
                            metadata={"record_id": existing_record["id"]},
                        )
                    except Exception:
                        pass
                    _insert_record_history(
                        c,
                        record_id=existing_record["id"],
                        action="conflict",
                        username="system",
                        old_ip_address=existing_record["ip_address"],
                        new_ip_address=record["ip_address"],
                        old_source=existing_record["source"],
                        new_source=new_source,
                        old_maintainer=existing_record["maintainer"],
                        new_maintainer=existing_record["maintainer"],
                    )
                c.execute(
                    """
                    UPDATE records
                    SET sync_conflict = 1,
                        sync_conflict_reason = ?,
                        last_modification_date = (NOW() + INTERVAL '4 hours')
                    WHERE id = ?
                    """,
                    (MULTI_SOURCE_A_CONFLICT_REASON, existing_record["id"]),
                )
                continue

            if (
                existing_record["ip_address"] != record["ip_address"]
                or existing_record["source"] != new_source
            ):
                if existing_record["ip_address"] != record["ip_address"]:
                    logger.info(
                        f"IP changed for {record['name']}: {existing_record['ip_address']} -> {record['ip_address']}"
                    )
                if existing_record["source"] != new_source:
                    logger.info(
                        f"Source changed for {record['name']}: {existing_record['source']} -> {new_source}"
                    )

                c.execute(
                    """
                    UPDATE records
                    SET ip_address = ?,
                        source = ?,
                        status = 'updated',
                        origin = 'automated',
                        last_modification_date = (NOW() + INTERVAL '4 hours')
                    WHERE name = ?
                    """,
                    (record["ip_address"], new_source, record["name"]),
                )

                _insert_record_history(
                    c,
                    record_id=existing_record["id"],
                    action="updated",
                    username="system",
                    old_ip_address=existing_record["ip_address"],
                    new_ip_address=record["ip_address"],
                    old_source=existing_record["source"],
                    new_source=new_source,
                    old_maintainer=existing_record["maintainer"],
                    new_maintainer=existing_record["maintainer"],
                )
            else:
                c.execute(
                    """
                    UPDATE records
                    SET status = 'unchanged',
                        origin = 'automated'
                    WHERE name = ?
                    """,
                    (record["name"],),
                )
        else:
            new_source = determine_source_with_cursor(c, record["ip_address"])
            c.execute(
                """
                INSERT INTO records (
                    name, ip_address, source, status, origin, sync_conflict, sync_conflict_reason,
                    creation_date, application_owner, maintainer, description
                )
                VALUES (?, ?, ?, 'unchanged', 'automated', 0, NULL, (NOW() + INTERVAL '4 hours'), '', '', '')
                RETURNING id
                """,
                (record["name"], record["ip_address"], new_source),
            )
            logger.info(f"Inserted new record for {record['name']}")

            inserted = c.fetchone()
            new_record_id = inserted[0] if inserted else None
            if new_record_id is None:
                raise RuntimeError("Failed to create record id while storing records.")

            _insert_record_history(
                c,
                record_id=new_record_id,
                action="created",
                username="system",
                new_ip_address=record["ip_address"],
                new_source=new_source,
            )

            _create_initial_pentest_row(
                c,
                record_id=new_record_id,
                dns_name=record["name"],
                ip_address=record["ip_address"],
                source=new_source,
            )
            logger.info(f"Created initial pentest data entry for record_id: {new_record_id}")

    if source_id is not None:
        c.execute(
            "SELECT DISTINCT fqdn FROM dns_observations WHERE source_id = ? AND rrtype = 'A'",
            (source_id,),
        )
        previously_seen = set()
        for row in c.fetchall():
            if isinstance(row, dict):
                previously_seen.add(row.get("fqdn"))
            else:
                previously_seen.add(row[0])
        live_names = set(latest_live_a_fqdns(db_path=db_path))
        live_names.update(current_names)
        names_to_mark_missing = sorted(name for name in (previously_seen - live_names) if name)
        if names_to_mark_missing:
            missing_placeholders = ",".join("?" for _ in names_to_mark_missing)
            c.execute(
                f"""
                UPDATE records
                SET status = 'missing'
                WHERE name IN ({missing_placeholders})
                  AND origin = 'automated'
                """,
                tuple(names_to_mark_missing),
            )
            c.execute(
                f"""
                INSERT INTO record_history (record_id, action, timestamp, username,
                                            old_ip_address, new_ip_address,
                                            old_source, new_source,
                                            old_maintainer, new_maintainer)
                SELECT id, 'deleted', (NOW() + INTERVAL '4 hours'), 'system',
                        ip_address, NULL,
                        source, NULL,
                        maintainer, NULL
                FROM records
                WHERE name IN ({missing_placeholders})
                  AND origin = 'automated'
                """,
                tuple(names_to_mark_missing),
            )
    else:
        placeholders = ",".join("?" for _ in current_names)
        if placeholders:
            c.execute(
                f"""
                UPDATE records
                SET status = 'missing'
                WHERE name NOT IN ({placeholders})
                  AND origin = 'automated'
                """,
                tuple(current_names),
            )
            c.execute(
                f"""
                INSERT INTO record_history (record_id, action, timestamp, username,
                                            old_ip_address, new_ip_address,
                                            old_source, new_source,
                                            old_maintainer, new_maintainer)
                SELECT id, 'deleted', (NOW() + INTERVAL '4 hours'), 'system',
                        ip_address, NULL,
                        source, NULL,
                        maintainer, NULL
                FROM records
                WHERE name NOT IN ({placeholders})
                  AND origin = 'automated'
                """,
                tuple(current_names),
            )

    conn.commit()
    conn.close()


def _assign_unassigned_env(cursor, record_id: int, application_id: Optional[int]) -> None:
    if not application_id:
        cursor.execute(
            "UPDATE records SET environment_id = NULL WHERE id = ?",
            (record_id,),
        )
        return
    from app.repositories.environments_repository import ensure_unassigned_environment

    env_id = ensure_unassigned_environment(cursor, application_id)
    if not env_id:
        return
    cursor.execute(
        """
        UPDATE records
        SET environment_id = ?, application_id = ?
        WHERE id = ? AND environment_id IS NULL
        """,
        (env_id, application_id, record_id),
    )


def _set_host_environment(
    cursor,
    record_id: int,
    application_id: Optional[int],
    environment_id: Optional[int],
) -> None:
    if not application_id:
        cursor.execute(
            "UPDATE records SET environment_id = NULL, application_id = NULL WHERE id = ?",
            (record_id,),
        )
        return
    if environment_id:
        cursor.execute(
            "SELECT id FROM environments WHERE id = ? AND application_id = ?",
            (environment_id, application_id),
        )
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE records
                SET environment_id = ?, application_id = ?
                WHERE id = ?
                """,
                (environment_id, application_id, record_id),
            )
            return
    cursor.execute("SELECT environment_id FROM records WHERE id = ?", (record_id,))
    current = cursor.fetchone()
    current_env = None
    if current:
        current_env = current["environment_id"] if isinstance(current, dict) else current[0]
    if current_env:
        cursor.execute(
            "SELECT id FROM environments WHERE id = ? AND application_id = ?",
            (current_env, application_id),
        )
        if cursor.fetchone():
            cursor.execute(
                "UPDATE records SET application_id = ? WHERE id = ?",
                (application_id, record_id),
            )
            return
    cursor.execute("UPDATE records SET environment_id = NULL WHERE id = ?", (record_id,))
    _assign_unassigned_env(cursor, record_id, application_id)


def create_manual_record(
    *,
    name: str,
    ip_address: str,
    application_owner: str,
    maintainer: str,
    description: str,
    open_ports: str,
    application_id: Optional[int],
    username: str,
    environment_id: Optional[int] = None,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    if application_id is not None:
        c.execute("SELECT id FROM applications WHERE id = ?", (application_id,))
        if not c.fetchone():
            conn.close()
            raise ValueError("application_not_found")

    c.execute("SELECT id FROM records WHERE LOWER(name) = LOWER(?)", (name,))
    existing = c.fetchone()
    if existing:
        conn.close()
        raise IntegrityError("Record already exists.")

    source = determine_source_with_cursor(c, ip_address)
    c.execute(
        """
        INSERT INTO records (
            name, ip_address, source, status, origin, sync_conflict, sync_conflict_reason,
            creation_date, last_modification_date, application_owner, maintainer, description, application_id
        )
        VALUES (?, ?, ?, 'unchanged', 'manual', 0, NULL,
                (NOW() + INTERVAL '4 hours'), (NOW() + INTERVAL '4 hours'), ?, ?, ?, ?)
        RETURNING id
        """,
        (name, ip_address, source, application_owner, maintainer, description, application_id),
    )
    inserted = c.fetchone()
    record_id = inserted[0] if inserted else None
    if record_id is None:
        conn.close()
        raise RuntimeError("Failed to create manual record.")
    _set_host_environment(c, record_id, application_id, environment_id)

    _insert_record_history(
        c,
        record_id=record_id,
        action="created",
        username=username,
        new_ip_address=ip_address,
        new_source=source,
        new_maintainer=maintainer,
    )
    _create_initial_pentest_row(
        c,
        record_id=record_id,
        dns_name=name,
        ip_address=ip_address,
        source=source,
        open_ports=open_ports,
    )

    conn.commit()
    conn.close()
    return {"id": record_id}


def resolve_manual_sync_conflict(
    *,
    record_id: int,
    imported_ip_address: str,
    username: str,
    db_path: str = DB_PATH,
) -> Optional[str]:
    return resolve_sync_conflict_with_ip(
        record_id=record_id,
        ip_address=imported_ip_address,
        username=username,
        require_manual=True,
        db_path=db_path,
    )


def resolve_sync_conflict_with_ip(
    *,
    record_id: int,
    ip_address: str,
    username: str,
    require_manual: bool = False,
    db_path: str = DB_PATH,
) -> Optional[str]:
    chosen_ip = str(ip_address or "").strip()
    if not chosen_ip:
        return "invalid_ip"

    conn = get_db_connection(db_path)
    c = conn.cursor()

    c.execute(
        """
        SELECT id, name, ip_address, source, maintainer, origin, sync_conflict
        FROM records
        WHERE id = ?
        """,
        (record_id,),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return "record_not_found"

    _, name, old_ip_address, old_source, maintainer, origin, sync_conflict = row
    if not bool(sync_conflict):
        conn.close()
        return "no_conflict"
    if require_manual and origin != "manual":
        conn.close()
        return "no_conflict"

    imported_source = determine_source_with_cursor(c, chosen_ip)
    next_origin = "automated"
    c.execute(
        """
        UPDATE records
        SET ip_address = ?,
            source = ?,
            origin = ?,
            sync_conflict = 0,
            sync_conflict_reason = NULL,
            status = CASE
                WHEN ip_address = ? AND source = ? THEN status
                ELSE 'updated'
            END,
            last_modification_date = (NOW() + INTERVAL '4 hours')
        WHERE id = ?
        """,
        (chosen_ip, imported_source, next_origin, chosen_ip, imported_source, record_id),
    )
    c.execute(
        """
        UPDATE pentest_data
        SET dns_name = ?, ip_address = ?, source = ?
        WHERE record_id = ?
        """,
        (name, chosen_ip, imported_source, record_id),
    )
    _insert_record_history(
        c,
        record_id=record_id,
        action="resolved_conflict",
        username=username,
        old_ip_address=old_ip_address,
        new_ip_address=chosen_ip,
        old_source=old_source,
        new_source=imported_source,
        old_maintainer=maintainer,
        new_maintainer=maintainer,
    )

    conn.commit()
    conn.close()
    return None


def update_record(
    record_id: int,
    application_owner: str,
    maintainer: str,
    description: str,
    open_ports: str,
    application_id: Optional[int],
    username: str,
    environment_id: Optional[int] = None,
    db_path: str = DB_PATH,
) -> Optional[str]:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    if application_id is not None:
        c.execute("SELECT id FROM applications WHERE id = ?", (application_id,))
        if not c.fetchone():
            conn.close()
            return "application_not_found"

    c.execute("SELECT maintainer FROM records WHERE id = ?", (record_id,))
    old_record = c.fetchone()
    if not old_record:
        conn.close()
        return "record_not_found"

    old_maintainer = old_record[0]

    c.execute(
        """
        UPDATE records
        SET application_owner = ?,
            maintainer = ?,
            description = ?,
            application_id = ?,
            last_modification_date = (NOW() + INTERVAL '4 hours')
        WHERE id = ?
        """,
        (application_owner, maintainer, description, application_id, record_id),
    )
    _set_host_environment(c, record_id, application_id, environment_id)

    c.execute("SELECT record_id FROM pentest_data WHERE record_id = ?", (record_id,))
    pentest_exists = c.fetchone()

    if pentest_exists:
        c.execute(
            """
            UPDATE pentest_data
            SET open_ports = ?
            WHERE record_id = ?
            """,
            (open_ports, record_id),
        )
    else:
        c.execute("SELECT name, ip_address, source FROM records WHERE id = ?", (record_id,))
        record_info = c.fetchone()
        if record_info:
            _create_initial_pentest_row(
                c,
                record_id=record_id,
                dns_name=record_info[0],
                ip_address=record_info[1],
                source=record_info[2],
                open_ports=open_ports,
            )

    if old_maintainer != maintainer:
        _insert_record_history(
            c,
            record_id=record_id,
            action="updated",
            username=username,
            old_maintainer=old_maintainer,
            new_maintainer=maintainer,
        )

    conn.commit()
    conn.close()
    return None


def delete_record(record_id: int, username: str, db_path: str = DB_PATH) -> bool:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    c.execute("SELECT ip_address, source, maintainer FROM records WHERE id = ?", (record_id,))
    record_data = c.fetchone()
    if not record_data:
        conn.close()
        return False

    old_ip_address, old_source, old_maintainer = record_data
    _insert_record_history(
        c,
        record_id=record_id,
        action="deleted",
        username=username,
        old_ip_address=old_ip_address,
        old_source=old_source,
        old_maintainer=old_maintainer,
    )

    c.execute("DELETE FROM pentest_findings WHERE record_id = ?", (record_id,))
    c.execute("DELETE FROM pentest_data WHERE record_id = ?", (record_id,))
    c.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return True


__all__ = [
    "MANUAL_SYNC_CONFLICT_REASON",
    "MULTI_SOURCE_A_CONFLICT_REASON",
    "create_manual_record",
    "delete_record",
    "resolve_manual_sync_conflict",
    "resolve_sync_conflict_with_ip",
    "store_records_in_db",
    "update_record",
]
