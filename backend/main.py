import os
import sqlite3
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import paramiko
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------------
# Utility function: parse zone file into record list
# ---------------------------------------------------------
def parse_bind_zone_file(filepath, hostname):
    """
    Naive parser for a BIND zone file.
    Returns a list of dictionaries. Each dictionary has keys:
      - name
      - source (WAF, Nginx, Cloud)
      - ip address
    """
    records = []
    rr_pattern = re.compile(
        r'^(\S+)\s+(\d+)?\s*(IN)?\s+A\s+(.+)$', re.IGNORECASE
    )

    with open(filepath, 'r') as f:
        for line in f:
            line = line.split(';', 1)[0].strip()
            if not line:
                continue

            match = rr_pattern.match(line)
            if match:
                name = match.group(1)  # Record name
                ip = match.group(4)    # IP Address
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
# Utility function: fetch file via SSH if requested
# ---------------------------------------------------------
import os
import shutil
import datetime

def fetch_zone_file_via_ssh(hostname, username, remote_path, local_path=None, key_path=None):
    """
    Fetches a file from a remote server via SSH/SFTP using Paramiko with public key authentication.
    Saves it locally with the same name as the source file, managing backups intelligently:
    - Only keep track of changes in the backup folder.
    - Delete duplicates if the file is identical to the most recent backup.
    - Keep a maximum of 100 backup files, deleting the oldest when necessary.
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Use the private key if specified, otherwise fallback to the default path
        private_key = paramiko.RSAKey.from_private_key_file(key_path or '~/.ssh/id_rsa')

        ssh.connect(hostname, username=username, pkey=private_key)

        # Automatically determine the local file name if not provided
        if local_path is None:
            local_path = os.path.basename(remote_path)

        # Create backup folder if it doesn't exist
        backup_folder = "backup"
        os.makedirs(backup_folder, exist_ok=True)

        # Backup old file if it exists
        if os.path.exists(local_path):
            # Get the most recent backup file, if any
            backups = sorted(
                [f for f in os.listdir(backup_folder) if f.startswith(local_path)],
                key=lambda x: os.path.getmtime(os.path.join(backup_folder, x)),
                reverse=True
            )
            most_recent_backup = os.path.join(backup_folder, backups[0]) if backups else None

            # Compare old file with the most recent backup
            with open(local_path, 'rb') as old_file:
                old_file_data = old_file.read()

            if most_recent_backup and os.path.exists(most_recent_backup):
                with open(most_recent_backup, 'rb') as recent_backup_file:
                    recent_backup_data = recent_backup_file.read()
                if old_file_data == recent_backup_data:
                    # Old file is identical to the most recent backup, delete it
                    os.remove(local_path)
                    print(f"Old file {local_path} matches the most recent backup. File deleted.")
                else:
                    # Move the old file to the backup folder
                    timestamp = datetime.datetime.now().strftime("%d.%m.%Y")
                    backup_name = f"{local_path}-{timestamp}"
                    backup_path = os.path.join(backup_folder, backup_name)
                    shutil.move(local_path, backup_path)
                    print(f"Old file {local_path} moved to {backup_path}")
            else:
                # Move the old file to the backup folder (no backups exist)
                timestamp = datetime.datetime.now().strftime("%d.%m.%Y")
                backup_name = f"{local_path}-{timestamp}"
                backup_path = os.path.join(backup_folder, backup_name)
                shutil.move(local_path, backup_path)
                print(f"Old file {local_path} moved to {backup_path}")

            # Manage the number of backup files
            if len(backups) >= 100:
                oldest_backup = os.path.join(backup_folder, backups[-1])
                os.remove(oldest_backup)
                print(f"Oldest backup {oldest_backup} deleted to maintain limit of 100 files.")

        # Fetch the new file from the remote server
        sftp = ssh.open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()
        ssh.close()

        print(f"File {remote_path} was successfully fetched to {local_path}.")
    except Exception as e:
        print(f"Error fetching file from SSH: {e}")
        raise

# ---------------------------------------------------------
# Utility function: create & populate SQLite DB
# ---------------------------------------------------------
def init_db(db_path='dns_records.db'):
    """
    Create the table for A records only.
    """
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

def store_records_in_db(records, db_path='dns_records.db'):
    """
    Merge new data into the database:
    - Add new records with their source.
    - Update IP for existing records and mark them as 'updated'.
    - Mark records as 'missing' if they are not in the new dataset.
    - Mark records as 'unchanged' if nothing changed.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Fetch existing records
    c.execute("SELECT name, ip_address, status FROM records")
    existing_records = {row[0]: {'ip_address': row[1], 'status': row[2]} for row in c.fetchall()}
    # print(existing_records)

    # Set of current domain names for comparison
    current_names = {record['name'] for record in records}

    # Add or update records
    for record in records:
        if record['name'] in existing_records:
            if existing_records[record['name']]['ip_address'] != record['ip_address']:
                print(f"IP changed for {record['name']}: {existing_records[record['name']]['ip_address']} -> {record['ip_address']}")
                # Update IP and mark as 'updated'
                c.execute("""
                    UPDATE records
                    SET ip_address = ?, status = 'updated', last_modification_date = datetime('now', '+4 hours')
                    WHERE name = ?
                """, (record['ip_address'], record['name']))
            else:
                # print(f"IP unchanged for {record['name']}: {record['ip_address']}")
                # No changes, mark as 'unchanged'
                c.execute("""
                    UPDATE records
                    SET status = 'unchanged'
                    WHERE name = ?
                """, (record['name'],))
        else:
            # Insert new record
            c.execute("""
                INSERT INTO records (name, ip_address, source, status, creation_date)
                VALUES (?, ?, ?, 'unchanged', datetime('now', '+4 hours'))
            """, (record['name'], record['ip_address'], record['source']))
            print(f"Inserted new record for {record['name']}")

    # Mark records as 'missing' if not in the current dataset
    c.execute("""
        UPDATE records
        SET status = 'missing'
        WHERE name NOT IN ({})
    """.format(','.join('?' * len(current_names))), tuple(current_names))

    conn.commit()
    conn.close()

# ---------------------------------------------------------
# Utility function: parse .env to get WAF and Nginx IPs
# ---------------------------------------------------------
# Parse .env to get WAF and Nginx IPs
WAF_IPS = os.getenv("WAF", "").split(",")
NGINX_IPS = os.getenv("NGINX", "").split(",")

def determine_source(ip):
    """
    Determine the source based on the IP address.
    """
    if ip in WAF_IPS:
        return "WAF"
    elif ip in NGINX_IPS:
        return "Nginx"
    else:
        return "Cloud"
    

# ---------------------------------------------------------
# Utility function: update source file every day
# ---------------------------------------------------------
import threading
import time

def periodic_update(interval, update_function):
    """
    Runs the update function periodically in a separate thread.
    
    Args:
        interval (int): Time in seconds between updates.
        update_function (callable): The function to run periodically.
    """
    def wrapper():
        update_function()
        # Restart the timer after the interval
        threading.Timer(interval, wrapper).start()
    
    # Start the initial timer
    threading.Timer(interval, wrapper).start()

def update_data():
    """
    Function to gather data (e.g., fetch zone file, update DB).
    This function supports both local and remote file fetching with public key authentication.
    """
    try:
        print(f"Starting data update at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Use remote details if specified, otherwise default to local file
        remote_details = {
            'hostname': os.getenv('REMOTE_HOST', ''),
            'username': os.getenv('REMOTE_USER', ''),
            'remote_path': os.getenv('REMOTE_PATH', ''),
            'key_path': os.getenv('REMOTE_KEY_PATH', '')  
        }

        local_file = os.getenv('DNS_HOSTNAME')
        use_remote = os.getenv("USE_REMOTE", "false").lower() == "true"

        if use_remote:
            # Fetch the zone file from remote server via SSH
            fetch_zone_file_via_ssh(
                hostname=remote_details['hostname'],
                username=remote_details['username'],
                remote_path=remote_details['remote_path'],
                key_path=remote_details['key_path']
            )
            zone_file_path = os.path.basename(remote_details['remote_path'])
        else:
            # Use local file
            zone_file_path = local_file

        # Parse the zone file into records
        hostname = os.path.basename(zone_file_path)  # Extract hostname
        records = parse_bind_zone_file(zone_file_path, hostname=hostname)

        # Store the records in the database
        store_records_in_db(records)

        print(f"Data update completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"Error during data update: {e}")

# ---------------------------------------------------------
# Flask App for serving & updating the DB
# ---------------------------------------------------------
app = Flask(__name__)
CORS(app, origins="http://localhost:3000") # Enable CORS for localhost

@app.route('/records', methods=['GET'])
def get_records():
    """
    GET /records
    Returns all DNS records in JSON form.
    """
    conn = sqlite3.connect('dns_records.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM records")
    rows = c.fetchall()
    conn.close()

    # Convert rows to list of dict
    records = [dict(ix) for ix in rows]
    return jsonify(records)

@app.route('/records/<int:record_id>', methods=['POST'])
def update_record(record_id):
    """
    POST /records/<record_id>
    Body JSON: { "name": "...", "ip_address": "...", "source": "..." }
    Updates a single DNS record in the DB after sanitization.
    """
    data = request.get_json(force=True)

    # --- Basic Input Sanitization ---
    # Remove any suspicious characters from string fields.
    # In real scenario, you might do stricter validations or use parameterized queries carefully.
    def sanitize_string(s):
        # Example: allow letters, digits, dots, dashes, underscores, spaces in name fields
        return re.sub(r'[^a-zA-Z0-9\.\-_ ]+', '', s)

    try:
        name = sanitize_string(data.get('name', ''))
        record_ip_address = sanitize_string(data.get('ip_address', ''))
        record_source = sanitize_string(data.get('source', '')) 

        conn = sqlite3.connect('dns_records.db')
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
    """
    DELETE /records/<record_id>
    Deletes a single DNS record from the DB.
    """
    try:
        conn = sqlite3.connect('dns_records.db')
        c = conn.cursor()
        c.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Record {record_id} deleted"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# ---------------------------------------------------------
# Main function to start the Flask server
# ---------------------------------------------------------
if __name__ == '__main__':
    # This block ensures the code below is executed only for the main process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        try:
            # Step 1: Initialize the database
            init_db()

            # Step 2: Populate initial records
            local_file = os.getenv("DNS_HOSTNAME")
            use_remote = os.getenv("USE_REMOTE", "false").lower() == "true"

            if use_remote:
                # Fetch the initial zone file via SSH
                remote_details = {
                    'hostname': os.getenv('REMOTE_HOST', ''),
                    'username': os.getenv('REMOTE_USER', ''),
                    'remote_path': os.getenv('REMOTE_PATH', ''),
                    'key_path': os.getenv('REMOTE_KEY_PATH', '')
                }

                fetch_zone_file_via_ssh(
                    hostname=remote_details['hostname'],
                    username=remote_details['username'],
                    remote_path=remote_details['remote_path'],
                    key_path=remote_details['key_path']
                )
                zone_file_path = os.path.basename(remote_details['remote_path'])
            else:
                # Use the local file
                zone_file_path = local_file

            # Parse the initial zone file and write to the database
            hostname = os.path.basename(zone_file_path)
            records = parse_bind_zone_file(zone_file_path, hostname=hostname)
            store_records_in_db(records)

            print(f"Initial records written to the database.")

            # Step 3: Start periodic updates every day
            periodic_update(int(os.getenv('UPDATE_TIME', 86400)), update_data)

        except Exception as e:
            print(f"Error during startup: {e}")

    # Step 4: Start the Flask server (always run, regardless of reloader process)
    print("Starting Flask server on http://127.0.0.1:5000...")
    app.run(debug=True)