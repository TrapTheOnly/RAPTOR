import logging
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import get_db_connection
from app.repositories.records_row_mapper import determine_source_with_cursor

logger = logging.getLogger(__name__)


def store_records_in_db(records: List[Dict[str, Any]], db_path: str = DB_PATH) -> None:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    c.execute("SELECT id, name, ip_address, source, maintainer FROM records")
    existing_records = {
        row[1]: {
            "id": row[0],
            "ip_address": row[2],
            "source": row[3],
            "maintainer": row[4],
        }
        for row in c.fetchall()
    }

    current_names = {r["name"] for r in records}

    for record in records:
        if record["name"] in existing_records:
            existing_record = existing_records[record["name"]]
            new_source = determine_source_with_cursor(c, record["ip_address"])

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
                    SET ip_address = ?, source = ?, status = 'updated', last_modification_date = (NOW() + INTERVAL '4 hours')
                    WHERE name = ?
                    """,
                    (record["ip_address"], new_source, record["name"]),
                )

                c.execute(
                    """
                    INSERT INTO record_history (record_id, action, timestamp, username,
                                               old_ip_address, new_ip_address,
                                               old_source, new_source,
                                               old_maintainer, new_maintainer)
                    VALUES (?, 'updated', (NOW() + INTERVAL '4 hours'), ?,
                            ?, ?,
                            ?, ?,
                            ?, ?)
                    """,
                    (
                        existing_record["id"],
                        "system",
                        existing_record["ip_address"],
                        record["ip_address"],
                        existing_record["source"],
                        new_source,
                        existing_record["maintainer"],
                        existing_record["maintainer"],
                    ),
                )
            else:
                c.execute(
                    """
                    UPDATE records
                    SET status = 'unchanged'
                    WHERE name = ?
                    """,
                    (record["name"],),
                )
        else:
            new_source = determine_source_with_cursor(c, record["ip_address"])
            c.execute(
                """
                INSERT INTO records (name, ip_address, source, status, creation_date, application_owner, maintainer, description)
                VALUES (?, ?, ?, 'unchanged', (NOW() + INTERVAL '4 hours'), '', '', '')
                RETURNING id
                """,
                (record["name"], record["ip_address"], new_source),
            )
            logger.info(f"Inserted new record for {record['name']}")

            inserted = c.fetchone()
            new_record_id = inserted[0] if inserted else None
            if new_record_id is None:
                raise RuntimeError("Failed to create record id while storing records.")
            c.execute(
                """
                INSERT INTO record_history (record_id, action, timestamp, username,
                                           old_ip_address, new_ip_address,
                                           old_source, new_source,
                                           old_maintainer, new_maintainer)
                VALUES (?, 'created', (NOW() + INTERVAL '4 hours'), ?,
                        NULL, ?,
                        NULL, ?,
                        NULL, NULL)
                """,
                (
                    new_record_id,
                    "system",
                    record["ip_address"],
                    new_source,
                ),
            )

            c.execute(
                """
                INSERT INTO pentest_data (record_id, dns_name, ip_address, source)
                VALUES (?, ?, ?, ?)
                """,
                (new_record_id, record["name"], record["ip_address"], new_source),
            )
            logger.info(f"Created initial pentest data entry for record_id: {new_record_id}")

    placeholders = ",".join("?" for _ in current_names)
    if placeholders:
        c.execute(
            f"""
            UPDATE records
            SET status = 'missing'
            WHERE name NOT IN ({placeholders})
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
            """,
            tuple(current_names),
        )

    conn.commit()
    conn.close()


def update_record(
    record_id: int,
    application_owner: str,
    maintainer: str,
    description: str,
    open_ports: str,
    application_id: Optional[int],
    username: str,
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
            c.execute(
                """
                INSERT INTO pentest_data (record_id, dns_name, ip_address, source, open_ports)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record_id, record_info[0], record_info[1], record_info[2], open_ports),
            )

    if old_maintainer != maintainer:
        c.execute(
            """
            INSERT INTO record_history (record_id, action, timestamp, username,
                                       old_ip_address, new_ip_address,
                                       old_source, new_source,
                                       old_maintainer, new_maintainer)
            VALUES (?, 'updated', (NOW() + INTERVAL '4 hours'), ?,
                    NULL, NULL,
                    NULL, NULL,
                    ?, ?)
            """,
            (record_id, username, old_maintainer, maintainer),
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

    c.execute(
        """
        INSERT INTO record_history (record_id, action, timestamp, username,
                                   old_ip_address, new_ip_address,
                                   old_source, new_source,
                                   old_maintainer, new_maintainer)
        VALUES (?, 'deleted', (NOW() + INTERVAL '4 hours'), ?,
                ?, NULL,
                ?, NULL,
                ?, NULL)
        """,
        (record_id, username, old_ip_address, old_source, old_maintainer),
    )

    c.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return True


__all__ = ["delete_record", "store_records_in_db", "update_record"]
