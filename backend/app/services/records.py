import os
import re
import glob
import time
import shutil
import sqlite3
import datetime
import logging
from typing import List, Dict, Optional

from ..config import DB_PATH, BACKUP_FOLDER, SHARED_PATH

logger = logging.getLogger(__name__)


def determine_source(ip: str) -> str:
    """
    Look up the IP in ip_sources. If found, return its source_name, else "Other".
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT source_name FROM ip_sources WHERE ip_address = ?", (ip,))
    row = c.fetchone()
    conn.close()

    if row:
        return row[0]
    return "Other"


def parse_bind_zone_file(filepath: str, hostname: str) -> List[Dict[str, str]]:
    """
    Parse a BIND zone file containing A records. Blank/@ names map to the domain apex.
    """
    records = []
    rr_pattern = re.compile(
        r'^\s*'
        r'(?P<name>\S*)\s*'
        r'(?P<ttl>\d+)?\s*'
        r'(IN\s+)?A\s+'
        r'(?P<ip>[^\s]+)'
        r'.*$',
        re.IGNORECASE,
    )

    with open(filepath, "r") as f:
        for line in f:
            line = line.split(";", 1)[0].strip()
            if not line:
                continue

            match = rr_pattern.match(line)
            if match:
                raw_name = match.group("name").strip()
                ip = match.group("ip").strip()

                if not raw_name or raw_name in ("@", ".", "IN"):
                    raw_name = hostname
                else:
                    raw_name = f"{raw_name}.{hostname}"

                source = determine_source(ip)
                record = {"name": raw_name, "ip_address": ip, "source": source}
                records.append(record)

    return records


def extract_domain_from_filename(filename: str) -> Optional[str]:
    """Extract the domain name from a filename like 'example.com_A_Records'."""
    match = re.match(r"(.+?)_A_Records", os.path.basename(filename))
    return match.group(1) if match else None


def handle_zone_file_changes(new_zone_file_path: str, final_filename: str) -> Optional[str]:
    """
    Handle copying and backup of a new zone file to the final destination, keeping a
    rolling set of backups (max 100).
    """
    try:
        domain_name = extract_domain_from_filename(final_filename)
        domain_backup_folder = os.path.join(BACKUP_FOLDER, domain_name or "unknown")
        os.makedirs(domain_backup_folder, exist_ok=True)

        with open(new_zone_file_path, "rb") as f_new:
            new_file_data = f_new.read()

        if not os.path.exists(final_filename):
            backups = sorted(
                glob.glob(os.path.join(domain_backup_folder, "*.bak")),
                key=os.path.getmtime,
                reverse=True,
            )
            if backups:
                most_recent_backup = backups[0]
                with open(most_recent_backup, "rb") as f_old:
                    old_file_data = f_old.read()

                if old_file_data == new_file_data:
                    logger.info(
                        "No changes found. The new file is identical to the latest backup (%s).",
                        most_recent_backup,
                    )
                    return None
                logger.info(
                    "New zone file differs from most recent backup %s. Copying as live file...",
                    most_recent_backup,
                )
            else:
                logger.info(
                    "No existing backups found for domain %s. Treating file as new.",
                    domain_name,
                )

            shutil.copy2(new_zone_file_path, final_filename)
            logger.info("New zone file copied to: %s", final_filename)
            return final_filename

        with open(final_filename, "rb") as f_old:
            old_file_data = f_old.read()

        if old_file_data == new_file_data:
            logger.info(
                "No changes found. The new file is identical to the existing file at %s.",
                final_filename,
            )
            return final_filename

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{os.path.basename(final_filename)}-{timestamp}.bak"
        backup_path = os.path.join(domain_backup_folder, backup_filename)

        shutil.move(final_filename, backup_path)
        logger.info("Existing zone file backed up to: %s", backup_path)

        shutil.copy2(new_zone_file_path, final_filename)
        logger.info("New zone file copied to: %s", final_filename)

        all_backups = sorted(glob.glob(f"{domain_backup_folder}/*.bak"), key=os.path.getmtime)
        if len(all_backups) > 100:
            oldest_backup = all_backups[0]
            os.remove(oldest_backup)
            logger.info("Oldest backup deleted: %s", oldest_backup)

        return final_filename
    except Exception as e:
        logger.error("Error handling zone file changes for %s: %s", final_filename, e)
        return None


def store_records_in_db(records: List[Dict[str, str]], db_path: str = DB_PATH):
    """
    Merge new DNS records into the DB: add new, update changed, mark missing.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT id, name, ip_address, source, maintainer FROM records")
    existing_records = {
        row[1]: {"id": row[0], "ip_address": row[2], "source": row[3], "maintainer": row[4]}
        for row in c.fetchall()
    }

    current_names = {r["name"] for r in records}

    for record in records:
        if record["name"] in existing_records:
            existing_record = existing_records[record["name"]]
            new_source = determine_source(record["ip_address"])

            if (
                existing_record["ip_address"] != record["ip_address"]
                or existing_record["source"] != new_source
            ):
                if existing_record["ip_address"] != record["ip_address"]:
                    logger.info(
                        "IP changed for %s: %s -> %s",
                        record["name"],
                        existing_record["ip_address"],
                        record["ip_address"],
                    )
                if existing_record["source"] != new_source:
                    logger.info(
                        "Source changed for %s: %s -> %s",
                        record["name"],
                        existing_record["source"],
                        new_source,
                    )

                c.execute(
                    """
                    UPDATE records
                    SET ip_address = ?, source = ?, status = 'updated', last_modification_date = datetime('now', '+4 hours')
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
                    VALUES (?, 'updated', datetime('now', '+4 hours'), ?,
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
            new_source = determine_source(record["ip_address"])
            c.execute(
                """
                INSERT INTO records (name, ip_address, source, status, creation_date, application_owner, maintainer, description)
                VALUES (?, ?, ?, 'unchanged', datetime('now', '+4 hours'), '', '', '')
            """,
                (record["name"], record["ip_address"], new_source),
            )
            logger.info("Inserted new record for %s", record["name"])

            new_record_id = c.lastrowid
            c.execute(
                """
                INSERT INTO record_history (record_id, action, timestamp, username,
                                           old_ip_address, new_ip_address,
                                           old_source, new_source,
                                           old_maintainer, new_maintainer)
                VALUES (?, 'created', datetime('now', '+4 hours'), ?,
                        NULL, ?,
                        NULL, ?,
                        NULL, NULL)
            """,
                (new_record_id, "system", record["ip_address"], new_source),
            )

            c.execute(
                """
                INSERT INTO pentest_data (record_id, dns_name, ip_address, source)
                VALUES (?, ?, ?, ?)
            """,
                (new_record_id, record["name"], record["ip_address"], new_source),
            )
            logger.info("Created initial pentest data entry for record_id: %s", new_record_id)

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
            SELECT id, 'deleted', datetime('now', '+4 hours'), 'system',
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


def update_data():
    """
    Parse zone files in SHARED_PATH, merge records, and update DB state.
    """
    try:
        logger.info("Starting data update at %s", time.strftime("%Y-%m-%d %H:%M:%S"))

        zone_files = glob.glob(f"{SHARED_PATH}/*_A_Records")
        if not zone_files:
            logger.warning("No zone files found in shared path.")
            return

        all_records: List[Dict[str, str]] = []
        for zone_file in zone_files:
            domain = extract_domain_from_filename(zone_file)
            if not domain:
                logger.warning("Skipping invalid file name format: %s", zone_file)
                continue

            logger.info("Processing zone file for domain: %s", domain)
            final_zone_file_path = os.path.join(os.getenv("DATA_PATH", ""), os.path.basename(zone_file))
            final_zone_file = handle_zone_file_changes(zone_file, final_zone_file_path)
            if not final_zone_file:
                continue

            records_this_domain = parse_bind_zone_file(final_zone_file, domain)
            all_records.extend(records_this_domain)

        if all_records:
            store_records_in_db(all_records)
        else:
            logger.info("No valid records found in any zone file.")

        logger.info("Data update completed at %s", time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        logger.error("Error during data update: %s", e)


def add_user_to_system(username: str, email: str, role: str = "user", db_path: str = DB_PATH):
    """
    Add a user to the allowed_users table.
    """
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO allowed_users (username, email, added_date, role)
            VALUES (?, ?, datetime('now', '+4 hours'), ?)
        """,
            (username, email, role),
        )
        conn.commit()
        logger.info("User %s added to the system with role %s.", username, role)
        conn.close()
    except sqlite3.IntegrityError:
        raise ValueError(f"User {username} already exists in the system.")
    except Exception as e:
        raise RuntimeError(f"Error adding user {username}: {e}")
