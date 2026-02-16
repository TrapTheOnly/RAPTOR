import os
import atexit
import logging
import bcrypt
import secrets
import json
from dotenv import load_dotenv
load_dotenv()

import re
import time
import glob
import shutil
import sqlite3
import datetime
import threading
import hashlib
from flask_cors import CORS
from datetime import timedelta
from modules.db_backend import ensure_db_backend, assert_migration_marker_if_sqlite_present

ensure_db_backend()
assert_migration_marker_if_sqlite_present()
from modules.user import *
from modules.admin import *
from modules.offsec import *
from modules.permissions import (
    PERMISSIONS,
    ROLE_DEFAULTS,
    ROLE_OPTIONAL,
    get_user_permissions,
    sanitize_extra_permissions,
    permission_required,
    user_has_permission
)
from modules.session_policy import (
    SESSION_IDLE_TIMEOUT_SECONDS,
    extend_session,
    get_session_timing,
    initialize_session_tracking,
    session_has_expired
)
from modules.docs_portal import (
    get_docs_access_matrix_for_user,
    get_docs_manifest_for_user,
    get_docs_page_for_user
)
from flask import Flask, request, jsonify, send_from_directory, session

# ---------------------------------------------------------
#! Paths for DB & backups (can be overridden by environment)
# ---------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_PATH = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
SHARED_PATH = os.getenv("SHARED_PATH", os.path.join(BASE_DIR, "shared"))
BACKUP_FOLDER = os.getenv("BACKUP_FOLDER", os.path.join(BASE_DIR, "backups"))
DB_PATH = os.path.join(DATA_PATH, "database.db")

# ---------------------------------------------------------
#! Configure logging
# ---------------------------------------------------------
log_folder = os.path.dirname(DB_PATH)
os.makedirs(log_folder, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_folder, "application.log"), mode='w'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

FAILED_LOGIN_ATTEMPT_LIMIT = max(1, int(os.getenv("FAILED_LOGIN_ATTEMPT_LIMIT", "5")))
LOGIN_LOCKOUT_BASE_MINUTES = max(1, int(os.getenv("LOGIN_LOCKOUT_BASE_MINUTES", "1")))
LOGIN_LOCKOUT_MAX_MINUTES = max(0, int(os.getenv("LOGIN_LOCKOUT_MAX_MINUTES", "0")))


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def normalize_auth_key(username):
    return str(username or "").strip().lower()


def get_login_lockout_status(username, db_path=DB_PATH):
    key = normalize_auth_key(username)
    if not key:
        return {
            "locked": False,
            "retry_after_seconds": 0,
            "remaining_attempts": FAILED_LOGIN_ATTEMPT_LIMIT
        }

    now_epoch = int(time.time())
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT failed_attempts, lockout_until_epoch
                FROM auth_lockouts
                WHERE username = ?
            """, (key,))
            row = c.fetchone()
            if not row:
                return {
                    "locked": False,
                    "retry_after_seconds": 0,
                    "remaining_attempts": FAILED_LOGIN_ATTEMPT_LIMIT
                }

            failed_attempts = max(0, int(row[0] or 0))
            lockout_until_epoch = max(0, int(row[1] or 0))
            retry_after_seconds = max(0, lockout_until_epoch - now_epoch)
            return {
                "locked": retry_after_seconds > 0,
                "retry_after_seconds": retry_after_seconds,
                "remaining_attempts": max(0, FAILED_LOGIN_ATTEMPT_LIMIT - failed_attempts)
            }
    except Exception as e:
        logger.error(f"Error reading login lockout state for '{key}': {e}")
        return {
            "locked": False,
            "retry_after_seconds": 0,
            "remaining_attempts": FAILED_LOGIN_ATTEMPT_LIMIT
        }


def register_failed_login_attempt(username, db_path=DB_PATH):
    key = normalize_auth_key(username)
    if not key:
        return {"locked": False, "retry_after_seconds": 0}

    now_epoch = int(time.time())
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT failed_attempts, lockout_level, lockout_until_epoch
                FROM auth_lockouts
                WHERE username = ?
            """, (key,))
            row = c.fetchone()
            failed_attempts = max(0, int(row[0] or 0)) if row else 0
            lockout_level = max(0, int(row[1] or 0)) if row else 0
            lockout_until_epoch = max(0, int(row[2] or 0)) if row else 0

            if lockout_until_epoch > now_epoch:
                return {
                    "locked": True,
                    "retry_after_seconds": lockout_until_epoch - now_epoch
                }

            failed_attempts += 1
            lockout_triggered = False
            retry_after_seconds = 0

            if failed_attempts >= FAILED_LOGIN_ATTEMPT_LIMIT:
                computed_minutes = LOGIN_LOCKOUT_BASE_MINUTES * (2 ** lockout_level)
                lockout_minutes = (
                    min(LOGIN_LOCKOUT_MAX_MINUTES, computed_minutes)
                    if LOGIN_LOCKOUT_MAX_MINUTES > 0
                    else computed_minutes
                )
                retry_after_seconds = int(lockout_minutes * 60)
                lockout_until_epoch = now_epoch + retry_after_seconds
                lockout_level += 1
                failed_attempts = 0
                lockout_triggered = True

            if row:
                c.execute("""
                    UPDATE auth_lockouts
                    SET failed_attempts = ?,
                        lockout_level = ?,
                        lockout_until_epoch = ?,
                        updated_at = datetime('now')
                    WHERE username = ?
                """, (failed_attempts, lockout_level, lockout_until_epoch, key))
            else:
                c.execute("""
                    INSERT INTO auth_lockouts (
                        username, failed_attempts, lockout_level, lockout_until_epoch, updated_at
                    ) VALUES (?, ?, ?, ?, datetime('now'))
                """, (key, failed_attempts, lockout_level, lockout_until_epoch))
            conn.commit()

            return {
                "locked": lockout_triggered,
                "retry_after_seconds": retry_after_seconds,
                "remaining_attempts": max(0, FAILED_LOGIN_ATTEMPT_LIMIT - failed_attempts)
            }
    except Exception as e:
        logger.error(f"Error storing failed login attempt for '{key}': {e}")
        return {"locked": False, "retry_after_seconds": 0}


def clear_login_lockout_state(username, db_path=DB_PATH):
    key = normalize_auth_key(username)
    if not key:
        return
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM auth_lockouts WHERE username = ?", (key,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error clearing login lockout state for '{key}': {e}")


def invalid_credentials_response(username):
    lockout = register_failed_login_attempt(username)
    if lockout.get("locked"):
        return jsonify({
            "error": "Too many failed login attempts. Try again later.",
            "retry_after_seconds": int(lockout.get("retry_after_seconds") or 0)
        }), 429
    return jsonify({"error": "Invalid credentials"}), 401

# ---------------------------------------------------------
# Utility: figure out source from IP
# ---------------------------------------------------------
def determine_source(ip):
    """
    Look up the IP in our ip_sources table. If found, return its source_name.
    Otherwise, return "Other".

    Input: IP address
    Returns: Source name (or "Other")
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT source_name FROM ip_sources WHERE ip_address = ?", (ip,))
    row = c.fetchone()
    conn.close()

    if row:
        return row[0]
    return "Other"

# ---------------------------------------------------------
# Utility: parse BIND zone file
# ---------------------------------------------------------
def parse_bind_zone_file(filepath, hostname):
    """
    Parse a BIND zone file that contains A records, including lines
    with blank or '@' names. Any blank/'@' name is treated as the domain apex.

    Input: BIND zone file path, hostname (e.g. 'example.com')
    Returns: List of dictionaries with 'name', 'ip_address', 'source' keys.
    """
    records = []
    rr_pattern = re.compile(
        r'^\s*'                   # leading whitespace
        r'(?P<name>\S*)\s*'       # capture 'name' (possibly blank)
        r'(?P<ttl>\d+)?\s*'       # optional TTL
        r'(IN\s+)?A\s+'           # 'IN' optional, then 'A'
        r'(?P<ip>[^\s]+)'         # capture IP
        r'.*$',                   # ignore the rest (if any)
        re.IGNORECASE
    )

    with open(filepath, 'r') as f:
        for line in f:
            line = line.split(';', 1)[0].strip()
            if not line:
                continue

            match = rr_pattern.match(line)
            if match:
                raw_name = match.group('name').strip()
                ip = match.group('ip').strip()

                if not raw_name or raw_name in ('@', '.', 'IN'):
                    raw_name = hostname
                else:
                    raw_name = f"{raw_name}.{hostname}"

                source = determine_source(ip)
                full_name = raw_name
                record = {
                    "name": full_name,
                    "ip_address": ip,
                    "source": source
                }
                records.append(record)

    return records

# ---------------------------------------------------------
# Utility: handle local file updates & backup
# ---------------------------------------------------------
def handle_zone_file_changes(new_zone_file_path, final_filename):
    """
    Handles copying and backup of a new zone file to the final destination.
    - If final_filename doesn't exist, compare new file to the most recent backup in the domain folder.
    - If identical, treat it as 'no change'.
    - If different, copy as the live file (and optionally back up if there's an existing live file).
    - If final_filename exists, do a normal compare -> backup old -> copy new if changed.
    - Limit backups to 100 per domain.

    Input: new_zone_file_path, final_filename
    Returns: final_filename if copied, None if no changes.
    """
    try:
        # 1) Figure out domain folder for backups
        domain_name = extract_domain_from_filename(final_filename)
        domain_backup_folder = os.path.join(BACKUP_FOLDER, domain_name)
        os.makedirs(domain_backup_folder, exist_ok=True)

        # 2) Read the new file data once
        with open(new_zone_file_path, 'rb') as f_new:
            new_file_data = f_new.read()

        # -----------------------------------------------------
        # CASE A: final_filename doesn't exist
        # -----------------------------------------------------
        if not os.path.exists(final_filename):
            # a) Check if there's a most recent .bak in domain_backup_folder
            backups = sorted(
                glob.glob(os.path.join(domain_backup_folder, '*.bak')),
                key=os.path.getmtime,
                reverse=True
            )
            if backups:
                most_recent_backup = backups[0]
                with open(most_recent_backup, 'rb') as f_old:
                    old_file_data = f_old.read()

                if old_file_data == new_file_data:
                    logger.info(f"No changes found. The new file is identical to the latest backup ({most_recent_backup}).")
                    return None
                else:
                    logger.info(f"New zone file differs from most recent backup {most_recent_backup}. Copying as live file...")
            else:
                logger.info(f"No existing backups found for domain {domain_name}. Treating file as new.")

            # b) Copy the new file as final_filename
            shutil.copy2(new_zone_file_path, final_filename)
            logger.info(f"New zone file copied to: {final_filename}")
            return final_filename

        # -----------------------------------------------------
        # CASE B: final_filename DOES exist
        # -----------------------------------------------------
        # Compare the existing final file with the new file
        with open(final_filename, 'rb') as f_old:
            old_file_data = f_old.read()

        # If files are identical, do nothing
        if old_file_data == new_file_data:
            logger.info(f"No changes found. The new file is identical to the existing file at {final_filename}.")
            return final_filename

        # If different -> backup the existing file and copy the new one
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{os.path.basename(final_filename)}-{timestamp}.bak"
        backup_path = os.path.join(domain_backup_folder, backup_filename)

        # Move old final file to domain backup
        shutil.move(final_filename, backup_path)
        logger.info(f"Existing zone file backed up to: {backup_path}")

        # Now copy new file to final location
        shutil.copy2(new_zone_file_path, final_filename)
        logger.info(f"New zone file copied to: {final_filename}")

        # Manage backups: limit to 100
        all_backups = sorted(glob.glob(f"{domain_backup_folder}/*.bak"), key=os.path.getmtime)
        if len(all_backups) > 100:
            oldest_backup = all_backups[0]
            os.remove(oldest_backup)
            logger.info(f"Oldest backup deleted: {oldest_backup}")

        return final_filename

    except Exception as e:
        logger.error(f"Error handling zone file changes for {final_filename}: {e}")

# ---------------------------------------------------------
# Utility: initialize & store records in SQLite DB
# ---------------------------------------------------------
def init_db(db_path=DB_PATH):
    """
    Create the tables for A records, allowed users, IP sources,
    record history, pentest data and port scan history, if they do not exist.

    Input: db_path
    Returns: None
    """

    logger.info("Initializing database...")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # DNS records table
    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unchanged',
            creation_date TEXT NOT NULL,
            last_modification_date TEXT,
            application_owner TEXT DEFAULT '',
            maintainer TEXT DEFAULT '',
            description TEXT DEFAULT '',
            application_id INTEGER
        )
    """)
    c.execute("PRAGMA table_info(records)")
    record_columns = {row[1] for row in c.fetchall()}
    if "application_id" not in record_columns:
        c.execute("ALTER TABLE records ADD COLUMN application_id INTEGER")
        record_columns.add("application_id")

    # Allowed users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS allowed_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            added_date TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            auth_type TEXT NOT NULL DEFAULT 'ldap',
            password BLOB,
            must_reset INTEGER NOT NULL DEFAULT 0,
            permissions TEXT
        )
    """)
    # Ensure new columns exist for legacy DBs
    c.execute("PRAGMA table_info(allowed_users)")
    allowed_user_columns = {row[1] for row in c.fetchall()}
    if "auth_type" not in allowed_user_columns:
        c.execute("ALTER TABLE allowed_users ADD COLUMN auth_type TEXT NOT NULL DEFAULT 'ldap'")
    if "password" not in allowed_user_columns:
        c.execute("ALTER TABLE allowed_users ADD COLUMN password BLOB")
    if "must_reset" not in allowed_user_columns:
        c.execute("ALTER TABLE allowed_users ADD COLUMN must_reset INTEGER NOT NULL DEFAULT 0")
    if "permissions" not in allowed_user_columns:
        c.execute("ALTER TABLE allowed_users ADD COLUMN permissions TEXT")
    c.execute("UPDATE allowed_users SET auth_type = 'ldap' WHERE auth_type IS NULL OR auth_type = ''")

    # Applications table
    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_by TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Legacy data repair: old deployments may have name-only application mapping.
    if "application_name" in record_columns:
        c.execute("""
            UPDATE records
            SET application_id = (
                SELECT a.id
                FROM applications a
                WHERE a.name = records.application_name
                LIMIT 1
            )
            WHERE (application_id IS NULL OR application_id = 0)
              AND application_name IS NOT NULL
              AND TRIM(application_name) != ''
              AND EXISTS (
                  SELECT 1
                  FROM applications a
                  WHERE a.name = records.application_name
              )
        """)
        c.execute("""
            UPDATE records
            SET application_name = (
                SELECT a.name
                FROM applications a
                WHERE a.id = records.application_id
                LIMIT 1
            )
            WHERE application_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM applications a
                  WHERE a.id = records.application_id
              )
        """)

    # IP sources table
    c.execute("""
        CREATE TABLE IF NOT EXISTS ip_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            ip_address TEXT NOT NULL UNIQUE
        )
    """)

    # Record history table
    c.execute("""
        CREATE TABLE IF NOT EXISTS record_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL,
            old_ip_address TEXT,
            new_ip_address TEXT,
            old_source TEXT,
            new_source TEXT,
            old_maintainer TEXT,
            new_maintainer TEXT
        )
    """)

    # Pentest data table
    c.execute("""
        CREATE TABLE IF NOT EXISTS pentest_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            dns_name TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            source TEXT NOT NULL,
            report_file TEXT,
            vulnerable INTEGER,
            tested_by TEXT,
            test_start_date TEXT,
            test_end_date TEXT,
            vulnerability_fixed INTEGER,
            service_desk_link TEXT,
            status TEXT NOT NULL DEFAULT 'Not Started',
            open_ports TEXT,
            notes TEXT,
            owasp_checklist TEXT,
            checklist_states TEXT,
            vulnerabilities TEXT,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
    """)
    # Ensure pentest columns exist for legacy DBs
    c.execute("PRAGMA table_info(pentest_data)")
    pentest_columns = {row[1] for row in c.fetchall()}
    if "vulnerabilities" not in pentest_columns:
        c.execute("ALTER TABLE pentest_data ADD COLUMN vulnerabilities TEXT")
    if "checklist_states" not in pentest_columns:
        c.execute("ALTER TABLE pentest_data ADD COLUMN checklist_states TEXT")
    if "generated_report_file" not in pentest_columns:
        c.execute("ALTER TABLE pentest_data ADD COLUMN generated_report_file TEXT")
    if "generated_report_template_id" not in pentest_columns:
        c.execute("ALTER TABLE pentest_data ADD COLUMN generated_report_template_id INTEGER")
    if "generated_report_generated_at" not in pentest_columns:
        c.execute("ALTER TABLE pentest_data ADD COLUMN generated_report_generated_at TEXT")

    # Service checklist templates table
    c.execute("""
        CREATE TABLE IF NOT EXISTS service_checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            service TEXT NOT NULL,
            source TEXT,
            auto_ports TEXT NOT NULL DEFAULT '[]',
            sections TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            is_system INTEGER NOT NULL DEFAULT 1,
            is_customized INTEGER NOT NULL DEFAULT 0,
            system_revision TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    c.execute("PRAGMA table_info(service_checklists)")
    checklist_columns = {row[1] for row in c.fetchall()}
    if "is_system" not in checklist_columns:
        c.execute("ALTER TABLE service_checklists ADD COLUMN is_system INTEGER NOT NULL DEFAULT 1")
    if "is_customized" not in checklist_columns:
        c.execute("ALTER TABLE service_checklists ADD COLUMN is_customized INTEGER NOT NULL DEFAULT 0")
    if "system_revision" not in checklist_columns:
        c.execute("ALTER TABLE service_checklists ADD COLUMN system_revision TEXT")

    # Report templates table
    c.execute("""
        CREATE TABLE IF NOT EXISTS report_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            template_json TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            is_system INTEGER NOT NULL DEFAULT 1,
            is_customized INTEGER NOT NULL DEFAULT 0,
            system_revision TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    c.execute("PRAGMA table_info(report_templates)")
    report_template_columns = {row[1] for row in c.fetchall()}
    if "description" not in report_template_columns:
        c.execute("ALTER TABLE report_templates ADD COLUMN description TEXT")
    if "is_system" not in report_template_columns:
        c.execute("ALTER TABLE report_templates ADD COLUMN is_system INTEGER NOT NULL DEFAULT 1")
    if "is_customized" not in report_template_columns:
        c.execute("ALTER TABLE report_templates ADD COLUMN is_customized INTEGER NOT NULL DEFAULT 0")
    if "system_revision" not in report_template_columns:
        c.execute("ALTER TABLE report_templates ADD COLUMN system_revision TEXT")

    # Metadata table for one-time startup actions
    c.execute("""
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Login lockout tracking table
    c.execute("""
        CREATE TABLE IF NOT EXISTS auth_lockouts (
            username TEXT PRIMARY KEY,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            lockout_level INTEGER NOT NULL DEFAULT 0,
            lockout_until_epoch INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)

    # Seed service checklist templates only once on first launch.
    # Afterwards the application uses DB data only.
    checklist_seed_key = "service_checklists_seeded_v2"
    c.execute("SELECT value FROM app_meta WHERE key = ?", (checklist_seed_key,))
    checklist_seeded = c.fetchone() is not None
    if not checklist_seeded:
        canonical_templates = get_default_service_checklists()
        canonical_by_key = {template["key"]: template for template in canonical_templates}

        c.execute("SELECT id, key, is_system, is_customized, system_revision FROM service_checklists")
        existing_rows = c.fetchall()
        existing_by_key = {row[1]: row for row in existing_rows}

        for key, template in canonical_by_key.items():
            system_revision = hashlib.sha256(
                json.dumps(template, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            auto_ports = json.dumps(template.get("auto_ports", []))
            sections = json.dumps(template.get("sections", []))
            existing = existing_by_key.get(key)
            if not existing:
                c.execute("""
                    INSERT INTO service_checklists (
                        key, name, service, source, auto_ports, sections, enabled,
                        is_system, is_customized, system_revision,
                        created_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, 0, ?, 'system', datetime('now', '+4 hours'), datetime('now', '+4 hours'))
                """, (
                    template["key"],
                    template["name"],
                    template["service"],
                    template.get("source", ""),
                    auto_ports,
                    sections,
                    system_revision
                ))
                continue

            existing_id, _, existing_is_system, existing_is_customized, existing_revision = existing
            if int(existing_is_customized or 0) == 0:
                c.execute("""
                    UPDATE service_checklists
                    SET name = ?, service = ?, source = ?, auto_ports = ?, sections = ?, enabled = 1,
                        is_system = 1, is_customized = 0, system_revision = ?,
                        updated_at = datetime('now', '+4 hours')
                    WHERE id = ?
                """, (
                    template["name"],
                    template["service"],
                    template.get("source", ""),
                    auto_ports,
                    sections,
                    system_revision,
                    existing_id
                ))
            else:
                c.execute("""
                    UPDATE service_checklists
                    SET is_system = 1,
                        system_revision = ?,
                        updated_at = datetime('now', '+4 hours')
                    WHERE id = ?
                """, (
                    system_revision,
                    existing_id
                ))

        for existing_id, existing_key, existing_is_system, existing_is_customized, _ in existing_rows:
            if int(existing_is_system or 0) == 1 and existing_key not in canonical_by_key:
                if int(existing_is_customized or 0) == 0:
                    c.execute("""
                        UPDATE service_checklists
                        SET enabled = 0, updated_at = datetime('now', '+4 hours')
                        WHERE id = ?
                    """, (existing_id,))

        c.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, datetime('now', '+4 hours'))",
            (checklist_seed_key,)
        )

    # Seed report templates only once on first launch.
    # Afterwards the application uses DB data only.
    report_seed_key = "report_templates_seeded_v1"
    c.execute("SELECT value FROM app_meta WHERE key = ?", (report_seed_key,))
    report_seeded = c.fetchone() is not None
    if not report_seeded:
        canonical_templates = get_default_report_templates()
        canonical_by_key = {template["key"]: template for template in canonical_templates}

        c.execute("SELECT id, key, is_system, is_customized FROM report_templates")
        existing_rows = c.fetchall()
        existing_by_key = {row[1]: row for row in existing_rows}

        for key, template in canonical_by_key.items():
            template_key = str(template.get("key", "")).strip().lower()
            template_name = str(template.get("name", "")).strip()
            template_description = str(template.get("description", "") or "").strip()
            blocks = template.get("blocks")
            if not template_key or not template_name or not isinstance(blocks, list) or len(blocks) == 0:
                logger.warning(f"Skipping invalid canonical report template '{key}'.")
                continue

            template_json = json.dumps(template)
            system_revision = build_report_template_revision(template)
            existing = existing_by_key.get(key)
            if not existing:
                c.execute("""
                    INSERT INTO report_templates (
                        key, name, description, template_json, enabled,
                        is_system, is_customized, system_revision,
                        created_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 1, 1, 0, ?, 'system', datetime('now', '+4 hours'), datetime('now', '+4 hours'))
                """, (
                    template_key,
                    template_name,
                    template_description,
                    template_json,
                    system_revision
                ))
                continue

            existing_id, _, existing_is_system, existing_is_customized = existing
            if int(existing_is_customized or 0) == 0:
                c.execute("""
                    UPDATE report_templates
                    SET name = ?, description = ?, template_json = ?, enabled = 1,
                        is_system = 1, is_customized = 0, system_revision = ?,
                        updated_at = datetime('now', '+4 hours')
                    WHERE id = ?
                """, (
                    template_name,
                    template_description,
                    template_json,
                    system_revision,
                    existing_id
                ))
            else:
                c.execute("""
                    UPDATE report_templates
                    SET is_system = 1,
                        system_revision = ?,
                        updated_at = datetime('now', '+4 hours')
                    WHERE id = ?
                """, (
                    system_revision,
                    existing_id
                ))

        for existing_id, existing_key, existing_is_system, existing_is_customized in existing_rows:
            if int(existing_is_system or 0) == 1 and existing_key not in canonical_by_key:
                if int(existing_is_customized or 0) == 0:
                    c.execute("""
                        UPDATE report_templates
                        SET enabled = 0, updated_at = datetime('now', '+4 hours')
                        WHERE id = ?
                    """, (existing_id,))

        c.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, datetime('now', '+4 hours'))",
            (report_seed_key,)
        )

    # Vulnerability categories table
    c.execute("""
        CREATE TABLE IF NOT EXISTS vuln_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_by TEXT,
            created_at TEXT NOT NULL,
            is_custom INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Seed vulnerability categories if empty
    c.execute("SELECT COUNT(*) FROM vuln_categories")
    if c.fetchone()[0] == 0:
        default_categories = [
            "SQL Injection",
            "Blind SQL Injection",
            "Stored XSS",
            "Reflected XSS",
            "DOM-based XSS",
            "Cross-Site Request Forgery (CSRF)",
            "Server-Side Request Forgery (SSRF)",
            "Remote Code Execution (RCE)",
            "Command Injection",
            "OS Command Injection",
            "Local File Inclusion (LFI)",
            "Remote File Inclusion (RFI)",
            "Path Traversal",
            "Directory Listing",
            "Insecure File Upload",
            "XML External Entity (XXE)",
            "XPath Injection",
            "LDAP Injection",
            "Server-Side Template Injection (SSTI)",
            "Insecure Deserialization",
            "Broken Authentication",
            "Weak Password Policy",
            "Credential Stuffing",
            "Session Fixation",
            "Session Hijacking",
            "Broken Access Control",
            "IDOR",
            "Privilege Escalation",
            "Open Redirect",
            "Clickjacking",
            "CORS Misconfiguration",
            "HTTP Request Smuggling",
            "HTTP Response Splitting",
            "Host Header Injection",
            "Prototype Pollution",
            "Business Logic Flaw",
            "Information Disclosure",
            "Sensitive Data Exposure",
            "Insufficient Logging & Monitoring",
            "Security Misconfiguration",
            "Insecure Defaults",
            "Rate Limiting Missing",
            "Brute Force",
            "JWT Weakness",
            "OAuth Misconfiguration",
            "SAML Misconfiguration",
            "API Mass Assignment",
            "API Rate Limit Bypass",
            "Insecure Direct Object Reference (IDOR)",
            "Cache Poisoning",
            "CRLF Injection",
            "HTTP Verb Tampering"
        ]
        for name in default_categories:
            c.execute("""
                INSERT INTO vuln_categories (name, created_by, created_at, is_custom)
                VALUES (?, ?, datetime('now', '+4 hours'), 0)
            """, (name, 'system'))

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

# ---------------------------------------------------------
# Utility: store records in SQLite DB
# ---------------------------------------------------------
def store_records_in_db(records, db_path=DB_PATH):
    """
    Merge new data into the DB:
      - Add new records if they're not present.
      - Update IP for existing records if changed => status = 'updated'.
      - Mark records as 'missing' if not in the new dataset.
      - Mark 'unchanged' otherwise.
    
    Input: list of dictionaries with 'name', 'ip_address', 'source' keys
    Returns: None
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Fetch ONLY the columns needed for comparison from existing records
    c.execute("SELECT id, name, ip_address, source, maintainer FROM records")
    existing_records = {row[1]: {
        'id': row[0],
        'ip_address': row[2],
        'source': row[3],
        'maintainer': row[4]
    } for row in c.fetchall()}

    current_names = {r['name'] for r in records}

    for record in records:
        if record['name'] in existing_records:
            existing_record = existing_records[record['name']]
            new_source = determine_source(record['ip_address']) # Determine new source

            # ONLY check and update ip_address and source (derived from IP)
            if (existing_record['ip_address'] != record['ip_address'] or
                existing_record['source'] != new_source):

                # Log the changes (optional, but good for debugging)
                if existing_record['ip_address'] != record['ip_address']:
                    logger.info(f"IP changed for {record['name']}: {existing_record['ip_address']} -> {record['ip_address']}")
                if existing_record['source'] != new_source:
                    logger.info(f"Source changed for {record['name']}: {existing_record['source']} -> {new_source}")

                # Update ONLY ip_address and source, and set status
                c.execute("""
                    UPDATE records
                    SET ip_address = ?, source = ?, status = 'updated', last_modification_date = datetime('now', '+4 hours')
                    WHERE name = ?
                """, (record['ip_address'], new_source, record['name']))

                # Log history (ip_address and source changes only)
                c.execute("""
                    INSERT INTO record_history (record_id, action, timestamp, username,
                                               old_ip_address, new_ip_address,
                                               old_source, new_source,
                                               old_maintainer, new_maintainer)
                    VALUES (?, 'updated', datetime('now', '+4 hours'), ?,
                            ?, ?,
                            ?, ?,
                            ?, ?)
                """, (existing_record['id'], 'system',  # Use 'system' for cron job updates
                      existing_record['ip_address'], record['ip_address'],
                      existing_record['source'], new_source,
                      existing_record['maintainer'], existing_record['maintainer'])) # Keep old maintainer

            else:
                # No changes from the zone file's perspective
                c.execute("""
                    UPDATE records
                    SET status = 'unchanged'
                    WHERE name = ?
                """, (record['name'],))

        else:  # New record (from zone file)
            new_source = determine_source(record['ip_address'])
            c.execute("""
                INSERT INTO records (name, ip_address, source, status, creation_date, application_owner, maintainer, description)
                VALUES (?, ?, ?, 'unchanged', datetime('now', '+4 hours'), '', '', '')
            """, (record['name'], record['ip_address'], new_source)) # Insert determined source
            logger.info(f"Inserted new record for {record['name']}")

            new_record_id = c.lastrowid

            # Log history (creation) - only ip_address and source
            c.execute("""
                INSERT INTO record_history (record_id, action, timestamp, username,
                                           old_ip_address, new_ip_address,
                                           old_source, new_source,
                                           old_maintainer, new_maintainer)
                VALUES (?, 'created', datetime('now', '+4 hours'), ?,
                        NULL, ?,
                        NULL, ?,
                        NULL, NULL)
            """, (new_record_id, 'system',  # Use 'system' for cron job
                  record['ip_address'], new_source))
            
            c.execute("""
                INSERT INTO pentest_data (record_id, dns_name, ip_address, source)
                VALUES (?, ?, ?, ?)
            """, (new_record_id, record['name'], record['ip_address'], new_source))
            logger.info(f"Created initial pentest data entry for record_id: {new_record_id}")

    # Mark as 'missing' (no change here)
    placeholders = ','.join('?' for _ in current_names)
    if placeholders:
        c.execute(f"""
            UPDATE records
            SET status = 'missing'
            WHERE name NOT IN ({placeholders})
        """, tuple(current_names))
        # Log 'missing' records in history.  This is a type of deletion.
        c.execute(f"""
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
        """, tuple(current_names))

    conn.commit()
    conn.close()

# ---------------------------------------------------------
# Utility: add user to the allowed_users table
# ---------------------------------------------------------
def add_user_to_system(username, email, role='user', auth_type='ldap', password_hash=None, must_reset=0, permissions=None, db_path=DB_PATH):
    """
    Add a user to the allowed_users table.

    Input: username, email, role (optional, defaults to 'user')
    Returns: None
    """
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        sanitized_permissions = sanitize_extra_permissions(role, permissions)
        c.execute("""
            INSERT INTO allowed_users (username, email, added_date, role, auth_type, password, must_reset, permissions)
            VALUES (?, ?, datetime('now', '+4 hours'), ?, ?, ?, ?, ?)
        """, (username, email, role, auth_type, password_hash, must_reset, json.dumps(sanitized_permissions)))
        conn.commit()
        logger.info(f"User {username} added to the system with role {role}.")
        conn.close()
    except sqlite3.IntegrityError:
        raise ValueError(f"User {username} already exists in the system.")
    except Exception as e:
        raise RuntimeError(f"Error adding user {username}: {e}")

# ---------------------------------------------------------
# Utility: periodic update scheduling
# ---------------------------------------------------------
update_stop_event = threading.Event()

def stop_periodic_update():
    update_stop_event.set()

atexit.register(stop_periodic_update)

def periodic_update(interval, update_function):
    """
    Runs `update_function` every `interval` seconds in a separate thread.

    Input: interval (seconds), update_function
    Returns: None
    """
    def wrapper():
        if update_stop_event.is_set():
            return
        update_function()
        timer = threading.Timer(interval, wrapper)
        timer.daemon = True
        timer.start()
    timer = threading.Timer(interval, wrapper)
    timer.daemon = True
    timer.start()

# ---------------------------------------------------------
# Utility: extract domain from filename
# ---------------------------------------------------------
def extract_domain_from_filename(filename):
    """
    Extract the domain name from the filename. Example:
    "example.com_A_Records" -> "example.com"

    Input: filename
    Returns: domain name (or None if not found)
    """
    match = re.match(r"(.+?)_A_Records", os.path.basename(filename))
    return match.group(1) if match else None

# ---------------------------------------------------------
# Main data update function: works with a local zone file
# ---------------------------------------------------------
def update_data():
    """
    1. Gather parsed records from all zone files.
    2. Store them in one pass so status is consistent.

    Returns: None
    """
    try:
        logger.info(f"Starting data update at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        shared_path = SHARED_PATH
        zone_files = glob.glob(f"{shared_path}/*_A_Records")
        if not zone_files:
            logger.warning("No zone files found in shared path.")
            return

        # 1) Parse each zone file, accumulate all records
        all_records = []
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

        # 2) Now store them all in one pass
        if all_records:
            store_records_in_db(all_records)
        else:
            logger.info("No valid records found in any zone file.")

        logger.info(f"Data update completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.error(f"Error during data update: {e}")

# ---------------------------------------------------------
#! Flask App
# ---------------------------------------------------------
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.getenv("SECRET_KEY")
app.permanent_session_lifetime = timedelta(seconds=SESSION_IDLE_TIMEOUT_SECONDS)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = _env_flag(
    "SESSION_COOKIE_SECURE",
    bool(os.getenv("CERT_FILE") and os.getenv("KEY_FILE"))
)
CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "*").split(",")}})

# ---------------------------------------------------------
#! Record API Endpoints
# ---------------------------------------------------------
@app.route('/dashboard/data', methods=['GET'])
@permission_required('view_dashboard')
def get_dashboard_data():
    """
    Returns dashboard-ready datasets in one authorized request so users with
    dashboard access do not need additional tab permissions for backend calls.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("""
                SELECT
                    r.id,
                    r.name,
                    r.source,
                    r.status,
                    r.last_modification_date
                FROM records r
            """)
            records = [dict(ix) for ix in c.fetchall()]

            c.execute("""
                SELECT
                    r.id AS recordId,
                    r.name,
                    r.source,
                    COALESCE(p.status, 'Not Started') AS status,
                    COALESCE(p.vulnerable, 0) AS vulnerable,
                    COALESCE(p.vulnerability_fixed, 0) AS vulnerability_fixed,
                    COALESCE(p.vulnerabilities, '') AS vulnerabilities,
                    p.tested_by,
                    p.test_start_date,
                    p.test_end_date
                FROM records r
                LEFT JOIN pentest_data p ON r.id = p.record_id
            """)
            pentest_records = [dict(ix) for ix in c.fetchall()]

            c.execute("SELECT source_name FROM ip_sources")
            ip_sources = [dict(ix) for ix in c.fetchall()]

        return jsonify({
            "records": records,
            "pentestRecords": pentest_records,
            "ipSources": ip_sources
        }), 200
    except Exception as e:
        logger.error(f"Error fetching dashboard datasets: {e}")
        return jsonify({"error": "Failed to load dashboard data."}), 500


@app.route('/api/records', methods=['GET'])
@permission_required('view_records')
def get_records():
    """
    Returns all records from the database with pentest data (including open_ports).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT
            r.id,
            r.name,
            r.ip_address,
            r.source,
            r.status,
            r.creation_date,
            r.last_modification_date,
            r.application_owner,
            r.maintainer,
            r.description,
            r.application_id,
            p.open_ports,
            a.name AS application_name
        FROM records r
        LEFT JOIN pentest_data p ON r.id = p.record_id
        LEFT JOIN applications a ON r.application_id = a.id
    """)
    rows = c.fetchall()
    conn.close()

    records = [dict(ix) for ix in rows]
    return jsonify(records)

@app.route('/api/records/<int:record_id>', methods=['POST'])
@permission_required('modify_records')
def update_record(record_id):
    """
    Update a record by ID (including open_ports in pentest_data).
    """
    data = parse_json_object()
    if not data:
        return jsonify({"error": "Invalid JSON payload."}), 400

    def sanitize_string(s):
        return re.sub(r'[^a-zA-Z0-9\.\-_ ]+', '', s)

    try:
        application_owner = sanitize_string(data.get('application_owner', ''))
        maintainer = sanitize_string(data.get('maintainer', ''))
        open_ports = data.get('open_ports', '')
        description = data.get('description', '')
        raw_application_id = data.get('application_id')
        application_id = None
        if raw_application_id not in (None, '', 'null'):
            try:
                application_id = int(raw_application_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid application ID."}), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        if application_id is not None:
            c.execute("SELECT id FROM applications WHERE id = ?", (application_id,))
            if not c.fetchone():
                conn.close()
                return jsonify({"error": "Application not found."}), 404

        c.execute("SELECT maintainer FROM records WHERE id = ?", (record_id,))
        old_record = c.fetchone()
        if not old_record:
            conn.close()
            return jsonify({"error": "Record not found"}), 404

        old_maintainer = old_record[0]

        # Update records table
        c.execute("""
            UPDATE records
            SET application_owner = ?,
                maintainer = ?,
                description = ?,
                application_id = ?,
                last_modification_date = datetime('now', '+4 hours')
            WHERE id = ?
        """, (application_owner, maintainer, description, application_id, record_id))

        # Update or insert open_ports in pentest_data
        c.execute("SELECT record_id FROM pentest_data WHERE record_id = ?", (record_id,))
        pentest_exists = c.fetchone()
        
        if pentest_exists:
            c.execute("""
                UPDATE pentest_data
                SET open_ports = ?
                WHERE record_id = ?
            """, (open_ports, record_id))
        else:
            # Get record details for initial pentest_data entry
            c.execute("SELECT name, ip_address, source FROM records WHERE id = ?", (record_id,))
            record_info = c.fetchone()
            if record_info:
                c.execute("""
                    INSERT INTO pentest_data (record_id, dns_name, ip_address, source, open_ports)
                    VALUES (?, ?, ?, ?, ?)
                """, (record_id, record_info[0], record_info[1], record_info[2], open_ports))

        if old_maintainer != maintainer:
            c.execute("""
                INSERT INTO record_history (record_id, action, timestamp, username,
                                           old_ip_address, new_ip_address,
                                           old_source, new_source,
                                           old_maintainer, new_maintainer)
                VALUES (?, 'updated', datetime('now', '+4 hours'), ?,
                        NULL, NULL,
                        NULL, NULL,
                        ?, ?)
            """, (record_id, session['username'],
                  old_maintainer, maintainer))

        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error updating record {record_id}: {e}")
        return jsonify({"error": "Failed to update record."}), 400

@app.route('/api/apps', methods=['GET'])
@permission_required('view_records')
def get_applications():
    """Return all application groups."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT id, name, created_by, created_at
                FROM applications
                ORDER BY name
            """)
            rows = c.fetchall()
        return jsonify([dict(ix) for ix in rows]), 200
    except Exception as e:
        logger.error(f"Error fetching applications: {e}")
        return jsonify({"error": "Failed to fetch applications."}), 500

@app.route('/api/apps', methods=['POST'])
@permission_required('manage_apps')
def create_application():
    """Create a new application group."""
    data = parse_json_object()
    if not data:
        return jsonify({"error": "Invalid JSON payload."}), 400
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Application name is required."}), 400

    sanitized = re.sub(r'[^a-zA-Z0-9\\-_. ]+', '', name)
    if not sanitized:
        return jsonify({"error": "Invalid application name."}), 400

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO applications (name, created_by, created_at)
                VALUES (?, ?, datetime('now', '+4 hours'))
            """, (sanitized, session.get('username', 'unknown')))
            conn.commit()
        return jsonify({"message": "Application created.", "name": sanitized}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Application name already exists."}), 409
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        return jsonify({"error": "Failed to create application."}), 500

@app.route('/api/apps/<int:app_id>', methods=['PUT'])
@permission_required('manage_apps')
def update_application(app_id):
    """Rename an application group."""
    data = parse_json_object()
    if not data:
        return jsonify({"error": "Invalid JSON payload."}), 400
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Application name is required."}), 400

    sanitized = re.sub(r'[^a-zA-Z0-9\\-_. ]+', '', name)
    if not sanitized:
        return jsonify({"error": "Invalid application name."}), 400

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, name FROM applications WHERE id = ?", (app_id,))
            existing_app = c.fetchone()
            if not existing_app:
                return jsonify({"error": "Application not found."}), 404

            old_name = str(existing_app["name"] or "").strip()
            c.execute("UPDATE applications SET name = ? WHERE id = ?", (sanitized, app_id))

            # Keep legacy denormalized schemas consistent (older DBs may still have this column).
            c.execute("PRAGMA table_info(records)")
            record_columns = {row["name"] for row in c.fetchall()}
            if "application_name" in record_columns:
                # Backfill old rows that were name-linked only, so future joins are stable.
                c.execute(
                    """
                    UPDATE records
                    SET application_id = ?
                    WHERE (application_id IS NULL OR application_id = 0)
                      AND application_name = ?
                    """,
                    (app_id, old_name)
                )

                c.execute(
                    """
                    UPDATE records
                    SET application_name = ?
                    WHERE application_id = ?
                       OR application_name = ?
                    """,
                    (sanitized, app_id, old_name)
                )

            conn.commit()
        return jsonify({"message": "Application updated.", "name": sanitized}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "Application name already exists."}), 409
    except Exception as e:
        logger.error(f"Error updating application: {e}")
        return jsonify({"error": "Failed to update application."}), 500

@app.route('/api/apps/<int:app_id>', methods=['DELETE'])
@permission_required('manage_apps')
def delete_application(app_id):
    """Delete an application group and unassign its records."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM applications WHERE id = ?", (app_id,))
            if not c.fetchone():
                return jsonify({"error": "Application not found."}), 404
            c.execute("UPDATE records SET application_id = NULL WHERE application_id = ?", (app_id,))
            c.execute("DELETE FROM applications WHERE id = ?", (app_id,))
            conn.commit()
        return jsonify({"message": "Application deleted."}), 200
    except Exception as e:
        logger.error(f"Error deleting application: {e}")
        return jsonify({"error": "Failed to delete application."}), 500

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
@permission_required('delete_records')
def delete_record(record_id):
    """
    Delete a record by ID.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Fetch *only needed* data BEFORE deleting
        c.execute("SELECT ip_address, source, maintainer FROM records WHERE id = ?", (record_id,))
        record_data = c.fetchone()
        if not record_data:
            conn.close()
            return jsonify({"error": "Record not found"}), 404

        old_ip_address, old_source, old_maintainer = record_data

        # Log as 'deleted' in record_history
        c.execute("""
            INSERT INTO record_history (record_id, action, timestamp, username,
                                       old_ip_address, new_ip_address,
                                       old_source, new_source,
                                       old_maintainer, new_maintainer)
            VALUES (?, 'deleted', datetime('now', '+4 hours'), ?,
                    ?, NULL,
                    ?, NULL,
                    ?, NULL)
        """, (record_id, session['username'],
              old_ip_address,
              old_source,
              old_maintainer))  # old_* values, new_* are NULL

        # Now, delete the record
        c.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Record {record_id} deleted"}), 200
    except Exception as e:
        logger.error(f"Error deleting record {record_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to delete record."}), 400

@app.route('/api/records/<int:record_id>/history', methods=['GET'])
@permission_required('view_record_details')
def get_record_history(record_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Important for getting dict-like results
    c = conn.cursor()
    c.execute("SELECT * FROM record_history WHERE record_id = ? ORDER BY timestamp DESC", (record_id,))
    rows = c.fetchall()
    conn.close()

    history = [dict(ix) for ix in rows]
    return jsonify(history)

@app.route('/api/records/<int:record_id>', methods=['GET'])
@permission_required('view_record_details')
def get_record_by_id(record_id):
    """Return one record (with open_ports and application_name) by numeric ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT
            r.id,
            r.name,
            r.ip_address,
            r.source,
            r.status,
            r.creation_date,
            r.last_modification_date,
            r.application_owner,
            r.maintainer,
            r.description,
            r.application_id,
            p.open_ports,
            a.name AS application_name
        FROM records r
        LEFT JOIN pentest_data p ON r.id = p.record_id
        LEFT JOIN applications a ON r.application_id = a.id
        WHERE r.id = ?
    """, (record_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return jsonify(dict(row))
    return jsonify({"error": "Record not found"}), 404

@app.route('/api/records/<string:domain>', methods=['GET'])
@permission_required('view_record_details')
def get_record_by_domain(domain):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT r.*, p.open_ports
        FROM records r
        LEFT JOIN pentest_data p ON r.id = p.record_id
        WHERE r.name = ?
    """, (domain,))
    row = c.fetchone()
    conn.close()

    if row:
        record = dict(row)
        return jsonify(record)
    else:
        return jsonify({"error": "Record not found"}), 404

# ---------------------------------------------------------
#! OffSec API Endpoints
# ---------------------------------------------------------
app.add_url_rule('/pentest/<int:record_id>', methods=['POST'], view_func=create_or_update_pentest_data)
app.add_url_rule('/pentest/records', methods=['GET'], view_func=get_pentest_data)
app.add_url_rule('/pentest/<int:record_id>', methods=['DELETE'], view_func=delete_pentest_data)
app.add_url_rule('/pentest/<int:record_id>/report', methods=['GET'], view_func=get_report)
app.add_url_rule('/pentest/<int:record_id>/report', methods=['DELETE'], view_func=delete_report_route)
app.add_url_rule('/pentest/<int:record_id>/generate-report', methods=['POST'], view_func=generate_report)
app.add_url_rule('/pentest/<int:record_id>/generated-report', methods=['GET'], view_func=get_generated_report)
app.add_url_rule('/pentest/<int:record_id>/generated-report', methods=['DELETE'], view_func=delete_generated_report_route)
app.add_url_rule('/pentest_users', methods=['GET'], view_func=get_pentest_users)
app.add_url_rule('/pentest/<int:record_id>/images', methods=['POST'], view_func=upload_pentest_image)
app.add_url_rule('/pentest/images/<string:filename>', methods=['GET'], view_func=get_pentest_image)
app.add_url_rule('/checklist-templates', methods=['GET'], view_func=get_checklist_templates)
app.add_url_rule('/checklist-templates', methods=['POST'], view_func=create_checklist_template)
app.add_url_rule('/checklist-templates/<int:template_id>', methods=['PUT'], view_func=update_checklist_template)
app.add_url_rule('/checklist-templates/<int:template_id>', methods=['DELETE'], view_func=delete_checklist_template)
app.add_url_rule('/checklist-templates/<int:template_id>/reset', methods=['POST'], view_func=reset_checklist_template_to_canonical)
app.add_url_rule('/report-templates', methods=['GET'], view_func=get_report_templates)
app.add_url_rule('/report-templates', methods=['POST'], view_func=create_report_template)
app.add_url_rule('/report-templates/<int:template_id>', methods=['PUT'], view_func=update_report_template)
app.add_url_rule('/report-templates/<int:template_id>', methods=['DELETE'], view_func=delete_report_template)
app.add_url_rule('/report-templates/<int:template_id>/reset', methods=['POST'], view_func=reset_report_template_to_canonical)

# ---------------------------------------------------------
#! Admin API Endpoints
# ---------------------------------------------------------
@app.route('/ldap-search', methods=['GET'])
@admin_required
def ldap_search():
    """
    Search for users in the LDAP directory.
    """
    query = request.args.get('query', '')
    if not query:
        return jsonify({"error": "Query parameter is required."}), 400
    query = query.lower()
    try:
        results = search_ldap_users(query)
        return jsonify({"results": results}), 200
    except Exception as e:
        logger.error(f"LDAP search failed: {e}")
        return jsonify({"error": "LDAP search failed."}), 500
    
@app.route('/add-user', methods=['POST'])
@admin_required
def add_user():
    """
    Add a user to the allowed_users table.
    """
    data = parse_json_object()
    username = str(data.get('username') or '').strip().lower()
    email = str(data.get('email') or '').strip().lower()
    role = str(data.get('role', 'user')).strip().lower()
    permissions = data.get('permissions', [])

    if not username:
        return jsonify({"error": "Username is required."}), 400
    if not email:
        return jsonify({"error": "Email is required."}), 400
    if not isinstance(permissions, list):
        return jsonify({"error": "Permissions must be a list."}), 400

    #Basic role validation
    if role not in ['user', 'pentester', 'manager']:
        return jsonify({"error": "Invalid role specified."}), 400

    try:
        add_user_to_system(username, email, role, auth_type='ldap', permissions=permissions)
        return jsonify({"message": f"User {username} added successfully with role {role}."}), 200
    except Exception as e:
        logger.error(f"Error adding user {username}: {e}")
        return jsonify({"error": "Failed to add user."}), 500

@app.route('/add-local-user', methods=['POST'])
@admin_required
def add_local_user():
    """
    Add a local (non-LDAP) user with a temporary password.
    """
    data = parse_json_object()
    username = str(data.get('username') or '').strip().lower()
    role = str(data.get('role', 'user')).strip().lower()
    permissions = data.get('permissions', [])

    if not username:
        return jsonify({"error": "Username is required."}), 400
    if username == ADMIN_USERNAME:
        return jsonify({"error": "Username is reserved."}), 400
    if role not in ['user', 'pentester', 'manager']:
        return jsonify({"error": "Invalid role specified."}), 400
    if not isinstance(permissions, list):
        return jsonify({"error": "Permissions must be a list."}), 400

    try:
        # Generate a temporary password (meets minimum length)
        temp_password = secrets.token_urlsafe(12)
        if len(temp_password) < 12:
            temp_password = temp_password + secrets.token_urlsafe(12)
        temp_password = temp_password[:32]

        hashed_password = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt())
        add_user_to_system(
            username=username,
            email='',
            role=role,
            auth_type='local',
            password_hash=hashed_password,
            must_reset=1,
            permissions=permissions
        )
        return jsonify({
            "message": f"Local user {username} created successfully.",
            "temp_password": temp_password
        }), 200
    except Exception as e:
        logger.error(f"Error adding local user {username}: {e}")
        return jsonify({"error": "Failed to create local user."}), 500
    
@app.route('/change-password', methods=['POST'])
@admin_required
def api_change_password():
    """
    Endpoint to change the admin password.
    """
    data = parse_json_object()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({"error": "Both current and new passwords are required."}), 400

    response, status_code = change_admin_password(current_password, new_password)
    return jsonify(response), status_code

@app.route('/admin-reset-password', methods=['POST'])
def api_admin_reset_password():
    """
    Endpoint to reset admin password after first login.
    """
    if not session.get('reset_required') or session.get('username') != ADMIN_USERNAME:
        return jsonify({"error": "Unauthorized"}), 403

    data = parse_json_object()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({"error": "New password is required."}), 400

    response, status_code = reset_admin_password(new_password)
    if status_code == 200:
        session['logged_in'] = True
        session['reset_required'] = False
        session['user_type'] = 'admin'
        return jsonify({
            "status": "logged_in",
            "username": session.get("username"),
            "user_type": "admin"
        }), 200
    return jsonify(response), status_code

@app.route('/user-reset-password', methods=['POST'])
def api_user_reset_password():
    """
    Endpoint for local users to reset their password after first login.
    """
    if not session.get('reset_required') or session.get('user_type') == 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    data = parse_json_object()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({"error": "New password is required."}), 400

    username = session.get('username')
    ok, msg = validate_password_nist(new_password, username=username)
    if not ok:
        return jsonify({"error": msg}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT password FROM allowed_users WHERE username = ?", (username,))
        result = c.fetchone()
        if not result or not result[0]:
            conn.close()
            return jsonify({"error": "User not found."}), 404
        if bcrypt.checkpw(new_password.encode(), result[0]):
            conn.close()
            return jsonify({"error": "New password must be different from the temporary password."}), 400
        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
        c.execute(
            "UPDATE allowed_users SET password = ?, must_reset = 0, auth_type = 'local' WHERE username = ?",
            (hashed_password, username)
        )
        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": "User not found."}), 404
        conn.commit()
        conn.close()
        session['logged_in'] = True
        session['reset_required'] = False
        return jsonify({
            "status": "logged_in",
            "username": username,
            "user_type": session.get("user_type")
        }), 200
    except Exception as e:
        logger.error(f"Error resetting password for user {username}: {e}")
        return jsonify({"error": "Failed to reset password."}), 500

@app.route('/existing-users', methods=['GET'])
@admin_required
def api_get_existing_users():
    """
    Endpoint to retrieve existing users.
    """
    response, status_code = get_existing_users()
    return jsonify(response), status_code

# In main.py
@app.route('/update-user-role', methods=['POST'])
@admin_required
def update_user_role():
    data = parse_json_object()
    username = normalize_auth_key(data.get('username'))
    new_role = str(data.get('role') or '').strip().lower()

    if not username or not new_role:
        return jsonify({"error": "Username and role are required"}), 400

    if new_role not in ['user', 'pentester', 'manager']:
        return jsonify({"error": "Invalid user role"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE allowed_users SET role = ?, permissions = ? WHERE username = ?",
            (new_role, json.dumps([]), username)
        )
        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": f"User {username} not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"message": f"Role for user {username} updated to {new_role}"}), 200
    except Exception as e:
        logger.error(f"Error updating role for user {username}: {e}")
        return jsonify({"error": "Failed to update user role"}), 500

@app.route('/update-user-permissions', methods=['POST'])
@admin_required
def update_user_permissions():
    data = parse_json_object()
    username = normalize_auth_key(data.get('username'))
    requested_permissions = data.get('permissions', [])

    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not isinstance(requested_permissions, list):
        return jsonify({"error": "Permissions must be a list"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT role FROM allowed_users WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": f"User {username} not found"}), 404

        role = (row[0] or 'user').lower()
        sanitized = sanitize_extra_permissions(role, requested_permissions)
        if set(requested_permissions) - set(sanitized):
            conn.close()
            return jsonify({"error": "Invalid permissions for role"}), 400

        c.execute(
            "UPDATE allowed_users SET permissions = ? WHERE username = ?",
            (json.dumps(sanitized), username)
        )
        conn.commit()
        conn.close()
        return jsonify({
            "message": "User permissions updated.",
            "permissions": sanitized
        }), 200
    except Exception as e:
        logger.error(f"Error updating permissions for user {username}: {e}")
        return jsonify({"error": "Failed to update user permissions"}), 500

@app.route('/delete-user', methods=['DELETE'])
@admin_required
def api_delete_user():
    """
    Endpoint to delete a user from the allowed_users table.
    """
    data = parse_json_object()
    username = normalize_auth_key(data.get('username'))

    if not username:
        return jsonify({"error": "Username is required."}), 400

    response, status_code = delete_user(username)
    return jsonify(response), status_code

@app.route('/manual-update', methods=['POST'])
@admin_required
def manual_update():
    """
    Manually trigger parsing of zone files from the shared folder.
    """
    try:
        update_data()
        return jsonify({"status": "success", "message": "Records updated successfully."}), 200
    except Exception as e:
        logger.error(f"Manual update error: {e}")
        return jsonify({"status": "error", "message": "Failed to update records."}), 500

@app.route('/pentest/reset-keep-open', methods=['POST'])
@admin_required
def reset_keep_open_vulnerabilities():
    """
    Reset pentest progress for all records except open vulnerabilities
    (vulnerable=1 and vulnerability_fixed=0). Requires explicit confirmation.
    """
    data = parse_json_object()
    confirm = data.get('confirm') is True
    phrase = data.get('phrase')
    required_phrase = "RESET ALL BUT OPEN VULNERABILITIES"
    if not confirm or phrase != required_phrase:
        return jsonify({"error": "Confirmation phrase required."}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Select rows to delete (everything except open vulnerabilities)
        c.execute("""
            SELECT p.*
            FROM pentest_data p
            WHERE NOT (p.vulnerable = 1 AND p.vulnerability_fixed = 0)
        """)
        rows = c.fetchall()

        report_deleted = 0
        report_delete_errors = 0
        generated_report_deleted = 0
        generated_report_delete_errors = 0

        for row in rows:
            if row["report_file"]:
                try:
                    delete_report(row["report_file"])
                    report_deleted += 1
                except Exception:
                    report_delete_errors += 1
            if "generated_report_file" in row.keys() and row["generated_report_file"]:
                try:
                    delete_report(row["generated_report_file"])
                    generated_report_deleted += 1
                except Exception:
                    generated_report_delete_errors += 1

        c.execute("""
            DELETE FROM pentest_data
            WHERE NOT (vulnerable = 1 AND vulnerability_fixed = 0)
        """)
        deleted_count = c.rowcount

        # Count remaining open vulnerabilities
        c.execute("""
            SELECT COUNT(*)
            FROM pentest_data
            WHERE vulnerable = 1 AND vulnerability_fixed = 0
        """)
        remaining_open = c.fetchone()[0]

        conn.commit()
        conn.close()

        stats = {
            "total_reset": deleted_count,
            "remaining_open": remaining_open,
            "reports_deleted": report_deleted,
            "report_delete_errors": report_delete_errors,
            "generated_reports_deleted": generated_report_deleted,
            "generated_report_delete_errors": generated_report_delete_errors
        }

        return jsonify({
            "message": "Pentest progress reset (open vulnerabilities preserved).",
            "stats": stats
        }), 200
    except Exception as e:
        logger.error(f"Error resetting pentest progress: {e}")
        return jsonify({"error": "Failed to reset pentest progress."}), 500
    
@app.route('/ip-sources', methods=['GET'])
@permission_required('manage_ip_sources')
def get_ip_sources():
    """
    Returns the full list of IP→Source mappings.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, source_name, ip_address FROM ip_sources")
        rows = c.fetchall()
        conn.close()

        # Convert rows to list of dicts
        ip_sources = [dict(row) for row in rows]
        return jsonify({"ip_sources": ip_sources}), 200
    except Exception as e:
        logger.error(f"Error retrieving IP sources: {e}")
        return jsonify({"error": "Failed to retrieve IP sources."}), 500
    
@app.route('/ip-sources', methods=['POST'])
@permission_required('manage_ip_sources')
def add_ip_source():
    """
    Adds a new IP→Source mapping.
    Also updates existing records if they have this IP (source=..., status='updated').
    JSON body: { "source_name": "...", "ip_address": "..." }
    """
    data = parse_json_object()
    source_name = str(data.get('source_name') or '').strip()
    ip_address = str(data.get('ip_address') or '').strip()

    if not source_name or not ip_address:
        return jsonify({"error": "source_name and ip_address are required."}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Insert new IP→Source mapping
        c.execute("""
            INSERT INTO ip_sources (source_name, ip_address)
            VALUES (?, ?)
        """, (source_name, ip_address))
        conn.commit()

        # Update existing records that match this IP
        c.execute("""
            UPDATE records
            SET source = ?,
                status = 'updated',
                last_modification_date = datetime('now', '+4 hours')
            WHERE ip_address = ?
        """, (source_name, ip_address))
        updated_count = c.rowcount

        conn.commit()
        conn.close()

        message = f"IP source {ip_address} added as '{source_name}'. {updated_count} existing record(s) updated."
        logger.info(message)
        return jsonify({"message": message}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": f"IP address {ip_address} is already defined."}), 400
    except Exception as e:
        logger.error(f"Error adding IP source: {e}")
        return jsonify({"error": "Failed to add IP source."}), 500
    
@app.route('/ip-sources', methods=['DELETE'])
@permission_required('manage_ip_sources')
def delete_ip_source():
    """
    Deletes an IP→Source mapping by ip_address.
    Also reverts any matching records to 'Other' with status='updated'.
    JSON body: { "ip_address": "..." }
    """
    data = parse_json_object()
    ip_address = str(data.get('ip_address') or '').strip()

    if not ip_address:
        return jsonify({"error": "ip_address is required."}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # First find the existing source_name for that IP (if any)
        c.execute("SELECT source_name FROM ip_sources WHERE ip_address = ?", (ip_address,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": f"No mapping found for IP {ip_address}."}), 404

        source_name = row[0]

        # Delete from ip_sources
        c.execute("DELETE FROM ip_sources WHERE ip_address = ?", (ip_address,))
        conn.commit()

        # Revert any existing records that had this IP => source='Other', status='updated'
        c.execute("""
            UPDATE records
            SET source = 'Other',
                status = 'updated',
                last_modification_date = datetime('now', '+4 hours')
            WHERE ip_address = ?
        """, (ip_address,))
        updated_count = c.rowcount
        conn.commit()
        conn.close()

        message = (f"IP source mapping for {ip_address} ('{source_name}') deleted. "
                   f"{updated_count} record(s) reverted to 'Other'.")
        logger.info(message)
        return jsonify({"message": message}), 200
    except Exception as e:
        logger.error(f"Error deleting IP source for {ip_address}: {e}")
        return jsonify({"error": "Failed to delete IP source."}), 500

# ---------------------------------------------------------
#! Vulnerability Categories API Endpoints
# ---------------------------------------------------------
@app.route('/vuln-categories', methods=['GET'])
@permission_required('view_pentest_page')
def get_vuln_categories():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, name, created_by, created_at, is_custom FROM vuln_categories ORDER BY name ASC")
        rows = c.fetchall()
        conn.close()
        return jsonify({"categories": [dict(row) for row in rows]}), 200
    except Exception as e:
        logger.error(f"Error fetching vulnerability categories: {e}")
        return jsonify({"error": "Failed to fetch categories."}), 500

@app.route('/vuln-categories', methods=['POST'])
@permission_required('manage_vuln_categories')
def add_vuln_category():
    data = parse_json_object()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO vuln_categories (name, created_by, created_at, is_custom)
            VALUES (?, ?, datetime('now', '+4 hours'), 1)
        """, (name, session.get('username', 'unknown')))
        category_id = c.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"message": "Category added successfully.", "id": category_id, "name": name}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "Category already exists."}), 400
    except Exception as e:
        logger.error(f"Error adding vulnerability category: {e}")
        return jsonify({"error": "Failed to add category."}), 500

@app.route('/vuln-categories/<int:category_id>', methods=['DELETE'])
@permission_required('manage_vuln_categories')
def delete_vuln_category(category_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM vuln_categories WHERE id = ?", (category_id,))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": "Category not found."}), 404
        conn.commit()
        conn.close()
        return jsonify({"message": "Category deleted successfully."}), 200
    except Exception as e:
        logger.error(f"Error deleting vulnerability category: {e}")
        return jsonify({"error": "Failed to delete category."}), 500

# ---------------------------------------------------------
#! User Authentication Endpoints
# ---------------------------------------------------------
@app.route('/login', methods=['POST'])
def login():
    """
    Authenticate the user and set session variables.
    """
    data = parse_json_object()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = normalize_auth_key(data.get('username'))
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    lockout = get_login_lockout_status(username)
    if lockout.get("locked"):
        return jsonify({
            "error": "Too many failed login attempts. Try again later.",
            "retry_after_seconds": int(lockout.get("retry_after_seconds") or 0)
        }), 429

    # Check allowed users first
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, role, auth_type, password, must_reset FROM allowed_users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()

    if username == ADMIN_USERNAME:
        if admin_login(username, password):
            clear_login_lockout_state(username)
            session.permanent = True
            session['username'] = username
            session['user_type'] = 'admin'

            if admin_requires_password_reset(username):
                session['reset_required'] = True
                session['logged_in'] = False
                return jsonify({
                    "status": "password_reset_required",
                    "username": username,
                    "user_type": "admin",
                    "permissions": list(get_user_permissions(username, "admin"))
                }), 200

            session['logged_in'] = True
            session.pop('reset_required', None)
            initialize_session_tracking()
            return jsonify({
                "status": "logged_in",
                "username": username,
                "user_type": "admin",
                "permissions": list(get_user_permissions(username, "admin"))
            }), 200
        return invalid_credentials_response(username)

    if user:
        user_role = user[1] if user[1] else 'user'
        auth_type = user[2] if user[2] else 'ldap'
        password_hash = user[3]
        must_reset = bool(user[4])

        if auth_type == 'local':
            if not password_hash or not bcrypt.checkpw(password.encode(), password_hash):
                return invalid_credentials_response(username)

            clear_login_lockout_state(username)
            session.permanent = True
            session['username'] = user[0]
            session['user_type'] = user_role

            if must_reset:
                session['reset_required'] = True
                session['logged_in'] = False
                return jsonify({
                    "status": "password_reset_required",
                    "username": username,
                    "user_type": user_role,
                    "permissions": list(get_user_permissions(username, user_role))
                }), 200

            session['logged_in'] = True
            session.pop('reset_required', None)
            initialize_session_tracking()
            return jsonify({
                "status": "logged_in",
                "username": username,
                "user_type": user_role,
                "permissions": list(get_user_permissions(username, user_role))
            }), 200

        if ldap_authenticate(username, password):
            clear_login_lockout_state(username)
            session.permanent = True
            session['logged_in'] = True
            session['username'] = user[0]
            session['user_type'] = user_role
            session.pop('reset_required', None)
            initialize_session_tracking()
            return jsonify({
                "status": "logged_in",
                "username": username,
                "user_type": session['user_type'],
                "permissions": list(get_user_permissions(username, user_role))
            }), 200
        return invalid_credentials_response(username)
    return invalid_credentials_response(username)
    
@app.route('/session-status', methods=['GET'])
def session_status():
    """
    Check if the user is logged in.
    """
    if session.get('logged_in') and session_has_expired(update_activity=False):
        session.clear()
        return jsonify({"status": "logged_out"}), 401

    if session.get('reset_required'):
        return jsonify({
            "status": "password_reset_required",
            "username": session.get("username"),
            "user_type": session.get("user_type"),
            "permissions": list(get_user_permissions(session.get("username"), session.get("user_type")))
        }), 200
    if 'logged_in' in session and session['logged_in']:
        user_type = session.get('user_type')
        timing = get_session_timing(update_activity=False) or {}
        return jsonify({
            "status": "logged_in",
            "username": session.get("username"),
            "user_type": user_type,
            "permissions": list(get_user_permissions(session.get("username"), user_type)),
            "session_remaining_seconds": timing.get("remaining_seconds"),
            "active_remaining_seconds": timing.get("active_remaining_seconds"),
            "idle_remaining_seconds": timing.get("idle_remaining_seconds")
        }), 200
    return jsonify({"status": "logged_out"}), 401

@app.route('/session/extend', methods=['POST'])
def extend_logged_in_session():
    """
    Extend current session by configured extension window.
    """
    if not session.get('logged_in'):
        return jsonify({"status": "logged_out"}), 401
    if session_has_expired(update_activity=False):
        session.clear()
        return jsonify({"status": "logged_out"}), 401

    timing = extend_session()
    if not timing:
        return jsonify({"status": "logged_out"}), 401

    user_type = session.get('user_type')
    return jsonify({
        "status": "logged_in",
        "username": session.get("username"),
        "user_type": user_type,
        "permissions": list(get_user_permissions(session.get("username"), user_type)),
        "session_remaining_seconds": timing.get("remaining_seconds"),
        "active_remaining_seconds": timing.get("active_remaining_seconds"),
        "idle_remaining_seconds": timing.get("idle_remaining_seconds")
    }), 200

@app.route('/logout', methods=['POST'])
def logout():
    """
    Clear the session variables and log out the user.
    """
    session.clear()
    return jsonify({"status": "logged_out"}), 200


# ---------------------------------------------------------
#! Documentation API Endpoints
# ---------------------------------------------------------
@app.route('/docs/manifest', methods=['GET'])
@login_required_json
def docs_manifest():
    response, status_code = get_docs_manifest_for_user(
        session.get('username'),
        session.get('user_type')
    )
    return jsonify(response), status_code


@app.route('/docs/content/<string:section_slug>/<string:page_slug>', methods=['GET'])
@login_required_json
def docs_page_content(section_slug, page_slug):
    response, status_code = get_docs_page_for_user(
        section_slug=section_slug,
        page_slug=page_slug,
        username=session.get('username'),
        role=session.get('user_type')
    )
    return jsonify(response), status_code


@app.route('/docs/access-matrix', methods=['GET'])
@login_required_json
def docs_access_matrix():
    response, status_code = get_docs_access_matrix_for_user(
        session.get('username'),
        session.get('user_type')
    )
    return jsonify(response), status_code

# ---------------------------------------------------------
#! Frontend Routes
# ---------------------------------------------------------
@app.route('/')
@login_required_html
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(app.static_folder, 'index.html')

# ---------------------------------------------------------
#! Main
# ---------------------------------------------------------
if __name__ == '__main__':
        
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        init_db()
        init_admin_db()
        update_data()

        zone_update_interval = int(os.getenv('UPDATE_TIME', '86400'))
        periodic_update(zone_update_interval, update_data)

    port = os.getenv("APP_PORT")
    CERT_FILE = os.getenv("CERT_FILE")
    KEY_FILE = os.getenv("KEY_FILE")
    logger.info(f"Starting Flask server on port {port}...")
    if port == "5000":
        app.run(host='0.0.0.0', port=port, ssl_context=(CERT_FILE, KEY_FILE), debug=True)
    else:
        app.run(host='0.0.0.0', port=port, debug=True)
