import os
import sqlite3
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import shutil
import datetime
import threading
import time

# ---------------------------------------------------------
# Load environment variables from .env file
# ---------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------
# Paths for DB & backups (can be overridden by environment)
# ---------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", "/appdata/dns_records.db")
BACKUP_FOLDER = os.getenv("BACKUP_FOLDER", "/appdata/backup")

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
    Copies/renames a newly provided zone file to 'final_filename',
    while managing backups in BACKUP_FOLDER:
      - If 'final_filename' already exists, compare it to the most
        recent backup. If identical, remove the existing one to avoid duplication.
      - Otherwise, back it up with a timestamp before overwriting.
      - Maintain at most 100 backups.
    Returns the 'final_filename' where the zone file ends up.
    """

    os.makedirs(BACKUP_FOLDER, exist_ok=True)

    # If the final file doesn't exist yet, just copy new_zone_file_path => final_filename
    if not os.path.exists(final_filename):
        shutil.copy2(new_zone_file_path, final_filename)
        print(f"No existing zone file. Copied {new_zone_file_path} to {final_filename}")
        return final_filename

    # If final file exists, compare with latest backup
    with open(final_filename, 'rb') as old_file:
        old_file_data = old_file.read()
    with open(new_zone_file_path, 'rb') as new_file:
        new_file_data = new_file.read()

    # We only create a new backup if the "old file" differs from "new file"
    if old_file_data != new_file_data:
        # Find the existing backups for final_filename
        backups = sorted(
            [f for f in os.listdir(BACKUP_FOLDER) if f.startswith(os.path.basename(final_filename))],
            key=lambda x: os.path.getmtime(os.path.join(BACKUP_FOLDER, x)),
            reverse=True
        )
        most_recent_backup = os.path.join(BACKUP_FOLDER, backups[0]) if backups else None

        # Compare old file vs. most recent backup
        if most_recent_backup and os.path.exists(most_recent_backup):
            with open(most_recent_backup, 'rb') as recent_backup_file:
                recent_backup_data = recent_backup_file.read()
            if old_file_data == recent_backup_data:
                os.remove(final_filename)
                print(f"Existing zone file matches the most recent backup. File {final_filename} removed before overwriting.")
            else:
                # Move old final file to a new backup
                timestamp = datetime.datetime.now().strftime("%d.%m.%Y_%H%M%S")
                backup_name = f"{os.path.basename(final_filename)}-{timestamp}"
                backup_path = os.path.join(BACKUP_FOLDER, backup_name)
                shutil.move(final_filename, backup_path)
                print(f"Existing zone file moved to backup: {backup_path}")
        else:
            # No backups exist, so let's just rename the existing file
            timestamp = datetime.datetime.now().strftime("%d.%m.%Y_%H%M%S")
            backup_name = f"{os.path.basename(final_filename)}-{timestamp}"
            backup_path = os.path.join(BACKUP_FOLDER, backup_name)
            shutil.move(final_filename, backup_path)
            print(f"Existing zone file moved to backup: {backup_path}")

        # Copy the new file in place
        shutil.copy2(new_zone_file_path, final_filename)
        print(f"New zone file {new_zone_file_path} copied to {final_filename}")

        # Manage the number of backups (limit to 100)
        if len(backups) >= 100:
            oldest_backup = os.path.join(BACKUP_FOLDER, backups[-1])
            os.remove(oldest_backup)
            print(f"Oldest backup {oldest_backup} deleted (limit of 100).")
    else:
        print(f"No changes found. The new zone file is identical to {final_filename}.")

    return final_filename

# ---------------------------------------------------------
# Utility: Initialize & store records in SQLite DB
# ---------------------------------------------------------
def init_db(db_path=DB_PATH):
    """
    Create the table for A records if not existing.
    """
    # Ensure the parent directory exists
    print("Initializing database...")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    print(f"Using database at {db_path}")
    # List all files in the folder of db_path
    db_folder = os.path.dirname(db_path)
    files_in_db_folder = os.listdir(db_folder)
    print(f"Files in the database folder ({db_folder}): {files_in_db_folder}")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unchanged',
            creation_date TEXT NOT NULL,
            last_modification_date TEXT
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
                print(f"IP changed for {record['name']}: {existing_records[record['name']]['ip_address']} -> {record['ip_address']}")
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
                INSERT INTO records (name, ip_address, source, status, creation_date)
                VALUES (?, ?, ?, 'unchanged', datetime('now', '+4 hours'))
            """, (record['name'], record['ip_address'], record['source']))
            print(f"Inserted new record for {record['name']}")

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

# ---------------------------------------------------------
# Periodic update scheduling
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
# The main data update function: works with a local zone file
# ---------------------------------------------------------
def update_data():
    """
    1. Takes a local zone file path (from .env or default).
    2. Backs up the old zone file if changed, places the new file in a final location.
    3. Parses that final zone file and updates the DB.
    """
    try:
        print(f"Starting data update at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # .env holds e.g. DNS_HOSTNAME pointing to the new zone file
        new_zone_file_path = os.getenv("DNS_HOSTNAME", "/appdata/zonefile.db")
        if new_zone_file_path != "/appdata/zonefile.db": new_zone_file_path = "/usr/src/app/shared/" + new_zone_file_path
        print(f"Using zone file at {new_zone_file_path}")

        # Backup/replace final file with the new file
        final_zone_file = handle_zone_file_changes(new_zone_file_path, "/appdata/zonefile.db")

        # Parse the final zone file
        hostname = os.path.basename(final_zone_file)
        records = parse_bind_zone_file(final_zone_file, hostname=hostname)

        # Store in the database
        store_records_in_db(records)

        print(f"Data update completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"Error during data update: {e}")

# ---------------------------------------------------------
# Flask App
# ---------------------------------------------------------
app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app, origins="http://localhost:1337")
CORS(app, origins="http://localhost:3000")
CORS(app, origins="http://localhost:5000")

CORS(app, origins="http://kali01.azercell.com:1337")
CORS(app, origins="http://kali01.azercell.com:3000")
CORS(app, origins="http://kali01.azercell.com:5000")

CORS(app, origins="http://callisto.azercell.com:1337")
CORS(app, origins="http://callisto.azercell.com:3000")
CORS(app, origins="http://callisto.azercell.com:5000")


@app.route('/records', methods=['GET'])
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
def update_record(record_id):
    data = request.get_json(force=True)

    def sanitize_string(s):
        return re.sub(r'[^a-zA-Z0-9\.\-_ ]+', '', s)

    try:
        name = sanitize_string(data.get('name', ''))
        record_ip_address = sanitize_string(data.get('ip_address', ''))
        record_source = sanitize_string(data.get('source', ''))

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            UPDATE records
            SET name = ?,
                ip_address = ?,
                source = ?,
                last_modification_date = datetime('now', '+4 hours')
            WHERE id = ?
        """, (name, record_ip_address, record_source, record_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Record {record_id} deleted"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# ---------------------------------------------------------
# Serve the React App (if you're serving the build via Flask)
# ---------------------------------------------------------
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(app.static_folder, 'index.html')

# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
if __name__ == '__main__':
    try:
        # 1. Initialize the DB (will create /appdata if needed)
        init_db()

        # 2. Perform an initial update
        update_data()

        # 3. Set up periodic updates (default once per 24h = 86400s)
        interval = int(os.getenv('UPDATE_TIME', '86400'))
        periodic_update(interval, update_data)

    except Exception as e:
        print(f"Error during startup: {e}")

    # 4. Run Flask
    print("Starting Flask server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)