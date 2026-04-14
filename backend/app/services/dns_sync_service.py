import datetime
import glob
import logging
import os
import re
import shutil
import time
from typing import Any, Dict, List, Optional

from app.config import BACKUP_FOLDER, DATA_PATH, SHARED_PATH
from app.repositories.records_repository import determine_source, store_records_in_db

logger = logging.getLogger(__name__)


def extract_domain_from_filename(filename: str) -> Optional[str]:
    match = re.match(r"(.+?)_A_Records", os.path.basename(filename))
    return match.group(1) if match else None


def parse_bind_zone_file(filepath: str, hostname: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    rr_pattern = re.compile(
        r"^\s*"
        r"(?P<name>\S*)\s*"
        r"(?P<ttl>\d+)?\s*"
        r"(IN\s+)?A\s+"
        r"(?P<ip>[^\s]+)"
        r".*$",
        re.IGNORECASE,
    )

    with open(filepath, "r") as f:
        for line in f:
            line = line.split(";", 1)[0].strip()
            if not line:
                continue

            match = rr_pattern.match(line)
            if not match:
                continue

            raw_name = match.group("name").strip()
            ip = match.group("ip").strip()

            if not raw_name or raw_name in ("@", ".", "IN"):
                raw_name = hostname
            else:
                raw_name = f"{raw_name}.{hostname}"

            source = determine_source(ip)
            records.append(
                {
                    "name": raw_name,
                    "ip_address": ip,
                    "source": source,
                }
            )

    return records


def handle_zone_file_changes(new_zone_file_path: str, final_filename: str) -> Optional[str]:
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
                        f"No changes found. The new file is identical to the latest backup ({most_recent_backup})."
                    )
                    return None
                logger.info(
                    f"New zone file differs from most recent backup {most_recent_backup}. Copying as live file..."
                )
            else:
                logger.info(f"No existing backups found for domain {domain_name}. Treating file as new.")

            shutil.copy2(new_zone_file_path, final_filename)
            logger.info(f"New zone file copied to: {final_filename}")
            return final_filename

        with open(final_filename, "rb") as f_old:
            old_file_data = f_old.read()

        if old_file_data == new_file_data:
            logger.info(
                f"No changes found. The new file is identical to the existing file at {final_filename}."
            )
            return final_filename

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{os.path.basename(final_filename)}-{timestamp}.bak"
        backup_path = os.path.join(domain_backup_folder, backup_filename)

        shutil.move(final_filename, backup_path)
        logger.info(f"Existing zone file backed up to: {backup_path}")

        shutil.copy2(new_zone_file_path, final_filename)
        logger.info(f"New zone file copied to: {final_filename}")

        all_backups = sorted(glob.glob(f"{domain_backup_folder}/*.bak"), key=os.path.getmtime)
        if len(all_backups) > 100:
            oldest_backup = all_backups[0]
            os.remove(oldest_backup)
            logger.info(f"Oldest backup deleted: {oldest_backup}")

        return final_filename
    except Exception as e:
        logger.error(f"Error handling zone file changes for {final_filename}: {e}")
        return None


def update_data() -> None:
    try:
        logger.info(f"Starting data update at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        zone_files = glob.glob(f"{SHARED_PATH}/*_A_Records")
        if not zone_files:
            logger.warning("No zone files found in shared path.")
            return

        all_records: List[Dict[str, Any]] = []
        for zone_file in zone_files:
            domain = extract_domain_from_filename(zone_file)
            if not domain:
                logger.warning(f"Skipping invalid file name format: {zone_file}")
                continue

            logger.info(f"Processing zone file for domain: {domain}")
            final_zone_file_path = os.path.join(DATA_PATH, os.path.basename(zone_file))
            final_zone_file = handle_zone_file_changes(zone_file, final_zone_file_path)
            if not final_zone_file:
                continue

            records_this_domain = parse_bind_zone_file(final_zone_file, domain)
            all_records.extend(records_this_domain)

        if all_records:
            store_records_in_db(all_records)
        else:
            logger.info("No valid records found in any zone file.")

        logger.info(f"Data update completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.error(f"Error during data update: {e}")


def find_live_imported_record(name: str) -> Optional[Dict[str, str]]:
    target_name = str(name or "").strip().lower()
    if not target_name:
        return None

    zone_files = glob.glob(f"{DATA_PATH}/*_A_Records")
    for zone_file in zone_files:
        domain = extract_domain_from_filename(zone_file)
        if not domain:
            continue
        for record in parse_bind_zone_file(zone_file, domain):
            if str(record.get("name") or "").strip().lower() == target_name:
                return record
    return None
