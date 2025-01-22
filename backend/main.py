# import os
import sqlite3
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import paramiko

# ---------------------------------------------------------
# 1) Utility function: Parse zone file into record list
# ---------------------------------------------------------
def parse_bind_zone_file(filepath):
    """
    Naive parser for a BIND zone file.
    Returns a list of dictionaries. Each dictionary has keys:
      - name
      - ttl
      - record_class (usually 'IN')
      - record_type (e.g. SOA, NS, A, MX, etc.)
      - data (string containing the remainder of the record)
    """
    records = []
    # Simple regex to match resource records: name [TTL] class type data
    # This won't handle every corner case, but suffices as a demonstration.
    rr_pattern = re.compile(
        r'^(\S+)\s+(\d+)?\s*(IN)?\s+(SOA|NS|A|AAAA|CNAME|MX|TXT|PTR|SRV|CAA)\s+(.+)$',
        re.IGNORECASE
    )

    # We'll also want to capture the $TTL if present
    ttl_pattern = re.compile(r'^\$TTL\s+(\d+)', re.IGNORECASE)

    # Default TTL (can be overridden by $TTL)
    default_ttl = 3600

    with open(filepath, 'r') as f:
        for line in f:
            # Remove comments
            line = line.split(';', 1)[0].strip()
            if not line:
                continue

            # Check if there's a $TTL directive
            ttl_match = ttl_pattern.match(line)
            if ttl_match:
                default_ttl = int(ttl_match.group(1))
                continue

            # Match resource record lines
            match = rr_pattern.match(line)
            if match:
                name = match.group(1)
                ttl = match.group(2)
                if ttl is None:
                    ttl = default_ttl
                else:
                    ttl = int(ttl)
                record_class = match.group(3) or 'IN'
                record_type = match.group(4).upper()
                data = match.group(5).strip()
                record = {
                    'name': name,
                    'ttl': ttl,
                    'record_class': record_class,
                    'record_type': record_type,
                    'data': data
                }
                records.append(record)

    return records

# ---------------------------------------------------------
# 2) Utility function: fetch file via SSH if requested
# ---------------------------------------------------------
def fetch_zone_file_via_ssh(
    hostname, username, password, remote_path, local_path='remote.zone'
):
    """
    Fetches a file from a remote server via SSH/SFTP using Paramiko
    Saves it locally as local_path.
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)

        sftp = ssh.open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()
        ssh.close()

        print(f"File {remote_path} was successfully fetched to {local_path}.")
    except Exception as e:
        print(f"Error fetching file from SSH: {e}")
        raise

# ---------------------------------------------------------
# 3) Utility: create & populate SQLite DB
# ---------------------------------------------------------
def init_db(db_path='dns_records.db'):
    """
    Create the table if it doesn't exist.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ttl INTEGER NOT NULL,
            record_class TEXT NOT NULL,
            record_type TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def store_records_in_db(records, db_path='dns_records.db'):
    """
    Insert or update the DNS records in the database.
    For simplicity, we insert all records each time in this example.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Clear out old records or you could do merges, etc.
    c.execute("DELETE FROM records")

    for record in records:
        c.execute("""
            INSERT INTO records (name, ttl, record_class, record_type, data)
            VALUES (?, ?, ?, ?, ?)
        """, (record['name'], record['ttl'], record['record_class'],
              record['record_type'], record['data']))
    conn.commit()
    conn.close()

# ---------------------------------------------------------
# 4) Flask App for serving & updating the DB
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
    Body JSON: { "name": "...", "ttl": ..., "record_class": "...", "record_type": "...", "data": "..." }
    Updates a single DNS record in the DB after sanitization.
    """
    data = request.get_json(force=True)

    # --- Basic Input Sanitization (example) ---
    # Remove any suspicious characters from string fields.
    # In real scenario, you might do stricter validations or use parameterized queries carefully.
    def sanitize_string(s):
        # Example: allow letters, digits, dots, dashes, underscores, spaces in name fields
        return re.sub(r'[^a-zA-Z0-9\.\-_ ]+', '', s)

    try:
        name = sanitize_string(data.get('name', ''))
        ttl = int(data.get('ttl', 3600))
        record_class = sanitize_string(data.get('record_class', 'IN'))
        record_type = sanitize_string(data.get('record_type', 'A'))
        record_data = sanitize_string(data.get('data', ''))

        conn = sqlite3.connect('dns_records.db')
        c = conn.cursor()
        c.execute("""
            UPDATE records
            SET name = ?,
                ttl = ?,
                record_class = ?,
                record_type = ?,
                data = ?
            WHERE id = ?
        """, (name, ttl, record_class, record_type, record_data, record_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------------------------------------------------
# 5) Command-line entry point to parse local/remote and store
# ---------------------------------------------------------
def run_parser_and_serve(local_file=None, remote_info=None):
    """
    local_file: path to local zone file
    remote_info: dict with keys: hostname, username, password, remote_path
    """
    init_db()  # Ensure DB and table exist

    # If remote_info is provided, fetch the file from remote
    if remote_info:
        fetched_local = 'fetched_zone.zone'
        fetch_zone_file_via_ssh(
            hostname=remote_info['hostname'],
            username=remote_info['username'],
            password=remote_info['password'],
            remote_path=remote_info['remote_path'],
            local_path=fetched_local
        )
        zone_file_path = fetched_local
    else:
        zone_file_path = local_file

    # Parse the zone file into records
    records = parse_bind_zone_file(zone_file_path)
    # Store in DB
    store_records_in_db(records)

    # Start the Flask server
    print("Starting Flask server on http://127.0.0.1:5000...")
    app.run(debug=True)

if __name__ == '__main__':
    import sys
    
    # Example usage:
    # 1) Parse local file "example.com.zone" and serve
    #    python main.py local
    #
    # 2) Fetch remote file and serve
    #    python main.py remote
    
    mode = sys.argv[1] if len(sys.argv) > 1 else 'local'
    if mode == 'local':
        local_zone_file = 'example.com.zone'
        run_parser_and_serve(local_file=local_zone_file)
    elif mode == 'remote':
        # Hard-coded or you can read from environment variables or user input
        remote_details = {
            'hostname': '1.2.3.4',
            'username': 'root',
            'password': 'secret',
            'remote_path': '/etc/bind/example.com.zone'
        }
        run_parser_and_serve(remote_info=remote_details)
    else:
        print("Unknown mode. Use 'local' or 'remote'.")