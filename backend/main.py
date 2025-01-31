import os
import logging
from dotenv import load_dotenv
load_dotenv()

import sqlite3
import re
import glob
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import shutil
import datetime
import threading
import time
from datetime import timedelta
from userhandler import ldap_authenticate, login_required_json, login_required_html, search_ldap_users
from adminhandler import admin_required, init_admin_db, change_admin_password, get_existing_users, delete_user

# ---------------------------------------------------------
# Paths for DB & backups (can be overridden by environment)
# ---------------------------------------------------------
DB_PATH = os.getenv("DATA_PATH") + "database.db"
BACKUP_FOLDER = os.getenv("BACKUP_FOLDER")

# ---------------------------------------------------------
# Configure logging
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
WAF_IPS = os.getenv("WAF", "").split(",")
NGINX_IPS = os.getenv("NGINX", "").split(",")

def determine_source(ip):
    if ip in WAF_IPS:
        return "WAF"
    elif ip in NGINX_IPS:
        return "Nginx"
    else:
        return "Cloud"

# ---------------------------------------------------------
# Utility: parse BIND zone file
# ---------------------------------------------------------
def parse_bind_zone_file(filepath, hostname):
    """
    Naive parser for a BIND zone file.
    Returns a list of dictionaries. Each dictionary has keys:
      - name
      - ip_address
      - source (WAF, Nginx, Cloud)
    """
    records = []
    rr_pattern = re.compile(r'^(\S+)\s+(\d+)?\s*(IN)?\s+A\s+(.+)$', re.IGNORECASE)

    with open(filepath, 'r') as f:
        for line in f:
            line = line.split(';', 1)[0].strip()
            if not line:
                continue
            match = rr_pattern.match(line)
            if match:
                name = match.group(1)
                ip = match.group(4)
                source = determine_source(ip)
                full_name = f"{name}.{hostname}"
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
    - If the final file exists and is identical to the new file, no changes are made.
    - If different, the final file is backed up and the new file is copied in its place.
    - The number of backups is limited to 100 per domain.
    
    Args:
    new_zone_file_path (str): Path to the new zone file.
    final_filename (str): Destination path for the final zone file.

    Returns:
    str: The path of the final file.
    """
    try:
        # Extract domain name and create backup folder for this domain
        domain_name = extract_domain_from_filename(final_filename)
        domain_backup_folder = os.path.join(BACKUP_FOLDER, domain_name)
        os.makedirs(domain_backup_folder, exist_ok=True)

        # If the final file doesn't exist, just copy the new file
        if not os.path.exists(final_filename):
            shutil.copy2(new_zone_file_path, final_filename)
            logger.info(f"New zone file copied to: {final_filename}")
            return final_filename

        # Read the contents of both the existing and new files
        with open(final_filename, 'rb') as old_file, open(new_zone_file_path, 'rb') as new_file:
            old_file_data = old_file.read()
            new_file_data = new_file.read()

        # If files are identical, no changes are needed
        if old_file_data == new_file_data:
            logger.info(f"No changes found. The new file is identical to the existing file at {final_filename}.")
            return final_filename

        # Backup the existing file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{os.path.basename(final_filename)}-{timestamp}.bak"
        backup_path = os.path.join(domain_backup_folder, backup_filename)
        shutil.move(final_filename, backup_path)
        logger.info(f"Existing zone file backed up to: {backup_path}")

        # Copy the new file to the final location
        shutil.copy2(new_zone_file_path, final_filename)
        logger.info(f"New zone file copied to: {final_filename}")

        # Manage backups (limit to 100 backups per domain)
        backups = sorted(glob.glob(f"{domain_backup_folder}/*.bak"), key=os.path.getmtime)
        if len(backups) > 100:
            oldest_backup = backups[0]
            os.remove(oldest_backup)
            logger.info(f"Oldest backup deleted: {oldest_backup}")

        return final_filename

    except Exception as e:
        logger.error(f"Error handling zone file changes for {final_filename}: {e}")
        raise

# ---------------------------------------------------------
# Utility: initialize & store records in SQLite DB
# ---------------------------------------------------------
def init_db(db_path=DB_PATH):
    """
    Create the table for A records if not existing.
    """
    # Ensure the parent directory exists
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
            application_owner TEXT DEFAULT ''
        )
    """)

    # Allowed users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS allowed_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            added_date TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def store_records_in_db(records, db_path=DB_PATH):
    """
    Merge new data into the DB:
      - Add new records if they're not present.
      - Update IP for existing records if changed => status = 'updated'.
      - Mark records as 'missing' if not in the new dataset.
      - Mark 'unchanged' otherwise.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT name, ip_address, status FROM records")
    existing_records = {row[0]: {'ip_address': row[1], 'status': row[2]} for row in c.fetchall()}

    current_names = {r['name'] for r in records}

    # Insert or update
    for record in records:
        if record['name'] in existing_records:
            if existing_records[record['name']]['ip_address'] != record['ip_address']:
                logger.info(f"IP changed for {record['name']}: {existing_records[record['name']]['ip_address']} -> {record['ip_address']}")
                c.execute("""
                    UPDATE records
                    SET ip_address = ?, status = 'updated', last_modification_date = datetime('now', '+4 hours')
                    WHERE name = ?
                """, (record['ip_address'], record['name']))
            else:
                c.execute("""
                    UPDATE records
                    SET status = 'unchanged'
                    WHERE name = ?
                """, (record['name'],))
        else:
            c.execute("""
                INSERT INTO records (name, ip_address, source, status, creation_date, application_owner)
                VALUES (?, ?, ?, 'unchanged', datetime('now', '+4 hours'), '')
            """, (record['name'], record['ip_address'], record['source']))
            logger.info(f"Inserted new record for {record['name']}")

    # Mark as 'missing' anything not in the new dataset
    placeholders = ','.join('?' for _ in current_names)
    if placeholders:  # Only run if there's at least one record
        c.execute(f"""
            UPDATE records
            SET status = 'missing'
            WHERE name NOT IN ({placeholders})
        """, tuple(current_names))

    conn.commit()
    conn.close()

def add_user_to_system(username, email, db_path=DB_PATH):
    """
    Add a user to the allowed_users table.
    """
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO allowed_users (username, email, added_date)
            VALUES (?, ?, datetime('now', '+4 hours'))
        """, (username, email))
        conn.commit()
        logger.info(f"User {username} added to the system.")
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
    """
    match = re.match(r"(.+?)_A_Records", os.path.basename(filename))
    return match.group(1) if match else None

# ---------------------------------------------------------
# The main data update function: works with a local zone file
# ---------------------------------------------------------
def update_data():
    """
    1. Process all zone files in the shared path.
    2. For each file, parse and update records in the database.
    3. Back up each file separately if there are changes.
    """
    try:
        logger.info(f"Starting data update at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        shared_path = os.getenv("SHARED_PATH", "")
        zone_files = glob.glob(f"{shared_path}/*_A_Records")

        if not zone_files:
            logger.warning("No zone files found in shared path.")
            return

        for zone_file in zone_files:
            domain = extract_domain_from_filename(zone_file)
            if not domain:
                logger.warning(f"Skipping invalid file name format: {zone_file}")
                continue

            logger.info(f"Processing zone file for domain: {domain}")

            # Handle backup and parsing
            final_zone_file_path = os.path.join(os.getenv("DATA_PATH", ""), os.path.basename(zone_file))
            final_zone_file = handle_zone_file_changes(zone_file, final_zone_file_path)
            records = parse_bind_zone_file(final_zone_file, domain)

            # Store records in the database
            store_records_in_db(records)

        logger.info(f"Data update completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.error(f"Error during data update: {e}")

# ---------------------------------------------------------
# Flask App
# ---------------------------------------------------------
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.getenv("SECRET_KEY")
app.permanent_session_lifetime = timedelta(hours=1)
CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "*").split(",")}})

# ---------------------------------------------------------
# Record API Endpoints
# ---------------------------------------------------------
@app.route('/records', methods=['GET'])
@login_required_json
def get_records():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM records")
    rows = c.fetchall()
    conn.close()

    records = [dict(ix) for ix in rows]
    return jsonify(records)

@app.route('/records/<int:record_id>', methods=['POST'])
@login_required_json
def update_record(record_id):
    data = request.get_json(force=True)

    def sanitize_string(s):
        return re.sub(r'[^a-zA-Z0-9\.\-_ ]+', '', s)

    try:
        name = sanitize_string(data.get('name', ''))
        record_ip_address = sanitize_string(data.get('ip_address', ''))
        record_source = sanitize_string(data.get('source', ''))
        application_owner = sanitize_string(data.get('application_owner', ''))

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            UPDATE records
            SET name = ?,
                ip_address = ?,
                source = ?,
                application_owner = ?,
                last_modification_date = datetime('now', '+4 hours')
            WHERE id = ?
        """, (name, record_ip_address, record_source, application_owner, record_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error updating record {record_id}: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/records/<int:record_id>', methods=['DELETE'])
@admin_required
def delete_record(record_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Record {record_id} deleted"}), 200
    except Exception as e:
        logger.error(f"Error deleting record {record_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

# ---------------------------------------------------------
# Admin API Endpoints
# ---------------------------------------------------------
@app.route('/ldap-search', methods=['GET'])
@admin_required
def ldap_search():
    query = request.args.get('query').lower()
    try:
        results = search_ldap_users(query)
        return jsonify({"results": results}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/add-user', methods=['POST'])
@admin_required
def add_user():
    data = request.get_json()
    username = data.get('username').lower()
    email = data.get('email').lower()
    try:
        add_user_to_system(username, email)
        return jsonify({"message": f"User {username} added successfully."}), 200
    except Exception as e:
        logger.error(f"Error adding user {username}: {e}")
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


@app.route('/existing-users', methods=['GET'])
@admin_required
def api_get_existing_users():
    """
    Endpoint to retrieve existing users.
    """
    response, status_code = get_existing_users()
    return jsonify(response), status_code

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

# ---------------------------------------------------------
# User Authentication Endpoints
# ---------------------------------------------------------
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username').lower()
    password = data.get('password')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM allowed_users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    if not user and username != os.getenv("ADMIN_USERNAME"):
        return jsonify({"error": "Invalid credentials"}), 401

    if ldap_authenticate(username, password):
        session.permanent = True
        session['logged_in'] = True
        session['username'] = username
        user_type = "admin" if session.get('admin_logged_in') else "user"
        logger.info(f"User {username} logged in.")
        return jsonify({"status": "logged_in", "username": username, "user_type": user_type}), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401
    
@app.route('/session-status', methods=['GET'])
def session_status():
    """
    Check if the user is logged in.
    """
    if 'logged_in' in session and session['logged_in']:
        user_type = "admin" if session.get('admin_logged_in') else "user"
        return jsonify({"status": "logged_in", "username": session.get("username"), "user_type": user_type}), 200
    return jsonify({"status": "logged_out"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "logged_out"}), 200

# ---------------------------------------------------------
# Frontend Routes
# ---------------------------------------------------------
@app.route('/')
@login_required_html
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(app.static_folder, 'index.html')

# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
if __name__ == '__main__':
        
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        init_db()
        init_admin_db()
        update_data()
        interval = int(os.getenv('UPDATE_TIME', '86400'))
        periodic_update(interval, update_data)

    CERT_FILE = os.getenv("CERT_FILE")
    KEY_FILE = os.getenv("KEY_FILE")
    port = os.getenv("APP_PORT")
    logger.info(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port, ssl_context=(CERT_FILE, KEY_FILE), debug=True)