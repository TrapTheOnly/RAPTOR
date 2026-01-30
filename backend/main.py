import os
import logging
import bcrypt
import secrets
from dotenv import load_dotenv
load_dotenv()

import re
import time
import glob
import shutil
import sqlite3
import datetime
import threading
from flask_cors import CORS
from datetime import timedelta
from modules.user import *
from modules.admin import *
from modules.offsec import *
from flask import Flask, request, jsonify, send_from_directory, session

# ---------------------------------------------------------
#! Paths for DB & backups (can be overridden by environment)
# ---------------------------------------------------------
DB_PATH = os.getenv("DATA_PATH") + "database.db"
BACKUP_FOLDER = os.getenv("BACKUP_FOLDER")

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
            description TEXT DEFAULT ''
        )
    """)

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
            must_reset INTEGER NOT NULL DEFAULT 0
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
    c.execute("UPDATE allowed_users SET auth_type = 'ldap' WHERE auth_type IS NULL OR auth_type = ''")

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
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
    """)

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
def add_user_to_system(username, email, role='user', auth_type='ldap', password_hash=None, must_reset=0, db_path=DB_PATH):
    """
    Add a user to the allowed_users table.

    Input: username, email, role (optional, defaults to 'user')
    Returns: None
    """
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO allowed_users (username, email, added_date, role, auth_type, password, must_reset)
            VALUES (?, ?, datetime('now', '+4 hours'), ?, ?, ?, ?)
        """, (username, email, role, auth_type, password_hash, must_reset))
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
def periodic_update(interval, update_function):
    """
    Runs `update_function` every `interval` seconds in a separate thread.

    Input: interval (seconds), update_function
    Returns: None
    """
    def wrapper():
        update_function()
        threading.Timer(interval, wrapper).start()
    threading.Timer(interval, wrapper).start()

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

        shared_path = os.getenv("SHARED_PATH", "")
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
            final_zone_file_path = os.path.join(os.getenv("DATA_PATH", ""), os.path.basename(zone_file))
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
app.permanent_session_lifetime = timedelta(hours=1)
CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "*").split(",")}})

# ---------------------------------------------------------
#! Record API Endpoints
# ---------------------------------------------------------
@app.route('/api/records', methods=['GET'])
@login_required_json
def get_records():
    """
    Returns all records from the database with pentest data (including open_ports).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT r.*, p.open_ports
        FROM records r
        LEFT JOIN pentest_data p ON r.id = p.record_id
    """)
    rows = c.fetchall()
    conn.close()

    records = [dict(ix) for ix in rows]
    return jsonify(records)

@app.route('/api/records/<int:record_id>', methods=['POST'])
@login_required_json
def update_record(record_id):
    """
    Update a record by ID (including open_ports in pentest_data).
    """
    data = request.get_json(force=True)

    def sanitize_string(s):
        return re.sub(r'[^a-zA-Z0-9\.\-_ ]+', '', s)

    try:
        application_owner = sanitize_string(data.get('application_owner', ''))
        maintainer = sanitize_string(data.get('maintainer', ''))
        open_ports = data.get('open_ports', '')
        description = data.get('description', '')

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

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
                last_modification_date = datetime('now', '+4 hours')
            WHERE id = ?
        """, (application_owner, maintainer, description, record_id))

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
        return jsonify({"error": str(e)}), 400

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
@admin_required
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
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/records/<int:record_id>/history', methods=['GET'])
@login_required_json
def get_record_history(record_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Important for getting dict-like results
    c = conn.cursor()
    c.execute("SELECT * FROM record_history WHERE record_id = ? ORDER BY timestamp DESC", (record_id,))
    rows = c.fetchall()
    conn.close()

    history = [dict(ix) for ix in rows]
    return jsonify(history)

@app.route('/api/records/<string:domain>', methods=['GET'])
@login_required_json
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
app.add_url_rule('/pentest_users', methods=['GET'], view_func=get_pentest_users)

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
        return jsonify({"error": str(e)}), 500
    
@app.route('/add-user', methods=['POST'])
@admin_required
def add_user():
    """
    Add a user to the allowed_users table.
    """
    data = request.get_json()
    username = data.get('username').lower()
    email = data.get('email').lower()
    role = data.get('role', 'user').lower()

    #Basic role validation
    if role not in ['user', 'pentester']:
        return jsonify({"error": "Invalid role specified."}), 400

    try:
        add_user_to_system(username, email, role, auth_type='ldap')
        return jsonify({"message": f"User {username} added successfully with role {role}."}), 200
    except Exception as e:
        logger.error(f"Error adding user {username}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/add-local-user', methods=['POST'])
@admin_required
def add_local_user():
    """
    Add a local (non-LDAP) user with a temporary password.
    """
    data = request.get_json()
    username = data.get('username', '').lower().strip()
    role = data.get('role', 'user').lower()

    if not username:
        return jsonify({"error": "Username is required."}), 400
    if username == os.getenv("ADMIN_USERNAME"):
        return jsonify({"error": "Username is reserved."}), 400
    if role not in ['user', 'pentester']:
        return jsonify({"error": "Invalid role specified."}), 400

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
            must_reset=1
        )
        return jsonify({
            "message": f"Local user {username} created successfully.",
            "temp_password": temp_password
        }), 200
    except Exception as e:
        logger.error(f"Error adding local user {username}: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/change-password', methods=['POST'])
@admin_required
def api_change_password():
    """
    Endpoint to change the admin password.
    """
    data = request.get_json()
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
    if not session.get('reset_required') or session.get('username') != os.getenv("ADMIN_USERNAME"):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
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

    data = request.get_json()
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
    data = request.get_json()
    username = data.get('username')
    new_role = data.get('role')

    if not username or not new_role:
        return jsonify({"error": "Username and role are required"}), 400

    if new_role not in ['user', 'pentester']:
        return jsonify({"error": "Invalid user role"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE allowed_users SET role = ? WHERE username = ?", (new_role, username))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": f"User {username} not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"message": f"Role for user {username} updated to {new_role}"}), 200
    except Exception as e:
        logger.error(f"Error updating role for user {username}: {e}")
        return jsonify({"error": "Failed to update user role"}), 500

@app.route('/delete-user', methods=['DELETE'])
@admin_required
def api_delete_user():
    """
    Endpoint to delete a user from the allowed_users table.
    """
    data = request.get_json()
    username = data.get('username')

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
        logger.error(f"Manual update error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/pentest/reset-open-vulnerabilities', methods=['POST'])
@admin_required
def reset_open_vulnerabilities():
    """
    Export and reset pentest progress for open vulnerabilities (vulnerable=1 and vulnerability_fixed=0).
    Requires explicit confirmation.
    """
    data = request.get_json() or {}
    confirm = data.get('confirm') is True
    phrase = data.get('phrase')
    required_phrase = "RESET OPEN VULNERABILITIES"
    if not confirm or phrase != required_phrase:
        return jsonify({"error": "Confirmation phrase required."}), 400

    def csv_escape(value):
        if value is None:
            return ""
        text = str(value)
        if any(ch in text for ch in [',', '"', '\n']):
            return '"' + text.replace('"', '""') + '"'
        return text

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT p.*, r.name AS record_name, r.ip_address AS record_ip, r.source AS record_source
            FROM pentest_data p
            JOIN records r ON r.id = p.record_id
            WHERE p.vulnerable = 1 AND p.vulnerability_fixed = 0
        """)
        rows = c.fetchall()

        # Prepare export data before deletion
        header = [
            "Target Name",
            "IP Address",
            "Source",
            "Status",
            "Vulnerable",
            "Tested By",
            "Start Date",
            "End Date",
            "Fixed",
            "Service Desk",
            "Report"
        ]
        csv_lines = [",".join(header)]

        completed_count = 0
        in_progress_count = 0
        not_started_count = 0
        report_deleted = 0
        report_delete_errors = 0

        for row in rows:
            status = row["status"] or "Not Started"
            if status == "Completed":
                completed_count += 1
            elif status == "In Progress":
                in_progress_count += 1
            else:
                not_started_count += 1

            report_present = "Yes" if row["report_file"] else "No"
            csv_lines.append(",".join([
                csv_escape(row["record_name"] or row["dns_name"]),
                csv_escape(row["record_ip"] or row["ip_address"]),
                csv_escape(row["record_source"] or row["source"]),
                csv_escape(status),
                "Yes",
                csv_escape(row["tested_by"]),
                csv_escape(row["test_start_date"]),
                csv_escape(row["test_end_date"]),
                "No",
                csv_escape(row["service_desk_link"]),
                csv_escape(report_present)
            ]))

        # Delete report files before removing rows
        for row in rows:
            if row["report_file"]:
                try:
                    delete_report(row["report_file"])
                    report_deleted += 1
                except Exception:
                    report_delete_errors += 1

        # Delete pentest rows for open vulnerabilities
        c.execute("""
            DELETE FROM pentest_data
            WHERE vulnerable = 1 AND vulnerability_fixed = 0
        """)
        deleted_count = c.rowcount
        conn.commit()
        conn.close()

        stats = {
            "total_reset": deleted_count,
            "completed": completed_count,
            "in_progress": in_progress_count,
            "not_started": not_started_count,
            "reports_deleted": report_deleted,
            "report_delete_errors": report_delete_errors
        }

        return jsonify({
            "message": "Open vulnerability pentest progress reset.",
            "stats": stats,
            "csv": "\n".join(csv_lines)
        }), 200
    except Exception as e:
        logger.error(f"Error resetting open vulnerability progress: {e}")
        return jsonify({"error": "Failed to reset open vulnerabilities."}), 500
    
@app.route('/ip-sources', methods=['GET'])
@admin_required
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
        return jsonify({"error": str(e)}), 500
    
@app.route('/ip-sources', methods=['POST'])
@admin_required
def add_ip_source():
    """
    Adds a new IP→Source mapping.
    Also updates existing records if they have this IP (source=..., status='updated').
    JSON body: { "source_name": "...", "ip_address": "..." }
    """
    data = request.get_json()
    source_name = data.get('source_name')
    ip_address = data.get('ip_address')

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
        return jsonify({"error": str(e)}), 500
    
@app.route('/ip-sources', methods=['DELETE'])
@admin_required
def delete_ip_source():
    """
    Deletes an IP→Source mapping by ip_address.
    Also reverts any matching records to 'Other' with status='updated'.
    JSON body: { "ip_address": "..." }
    """
    data = request.get_json()
    ip_address = data.get('ip_address')

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
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------
#! User Authentication Endpoints
# ---------------------------------------------------------
@app.route('/login', methods=['POST'])
def login():
    """
    Authenticate the user and set session variables.
    """
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    username = username.lower()
    
    # Check allowed users first
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, role, auth_type, password, must_reset FROM allowed_users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    

    if username == os.getenv("ADMIN_USERNAME"):

        if admin_login(username, password):
            session.permanent = True
            session['username'] = username
            session['user_type'] = 'admin'

            if admin_requires_password_reset(username):
                session['reset_required'] = True
                session['logged_in'] = False
                return jsonify({
                    "status": "password_reset_required",
                    "username": username,
                    "user_type": "admin"
                }), 200

            session['logged_in'] = True
            session.pop('reset_required', None)
            return jsonify({"status": "logged_in", "username": username, "user_type": 'admin'}), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    if user:
        user_role = user[1] if user[1] else 'user'
        auth_type = user[2] if user[2] else 'ldap'
        password_hash = user[3]
        must_reset = bool(user[4])

        if auth_type == 'local':
            if not password_hash or not bcrypt.checkpw(password.encode(), password_hash):
                return jsonify({"error": "Invalid credentials"}), 401

            session.permanent = True
            session['username'] = user[0]
            session['user_type'] = user_role

            if must_reset:
                session['reset_required'] = True
                session['logged_in'] = False
                return jsonify({
                    "status": "password_reset_required",
                    "username": username,
                    "user_type": user_role
                }), 200

            session['logged_in'] = True
            session.pop('reset_required', None)
            return jsonify({"status": "logged_in", "username": username, "user_type": user_role}), 200

        if ldap_authenticate(username, password):
            session.permanent = True
            session['logged_in'] = True
            session['username'] = user[0]
            session['user_type'] = user_role
            session.pop('reset_required', None)
            return jsonify({"status": "logged_in", "username": username, "user_type": session['user_type']}), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    else:
        return jsonify({"error": "Invalid credentials"}), 401
    
@app.route('/session-status', methods=['GET'])
def session_status():
    """
    Check if the user is logged in.
    """
    if session.get('reset_required'):
        return jsonify({
            "status": "password_reset_required",
            "username": session.get("username"),
            "user_type": session.get("user_type")
        }), 200
    if 'logged_in' in session and session['logged_in']:
        user_type = session.get('user_type')
        return jsonify({"status": "logged_in", "username": session.get("username"), "user_type": user_type}), 200
    return jsonify({"status": "logged_out"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    """
    Clear the session variables and log out the user.
    """
    session.clear()
    return jsonify({"status": "logged_out"}), 200

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
