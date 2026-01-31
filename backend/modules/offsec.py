import os
import uuid
import re
import ftplib
import sqlite3
import logging
from io import BytesIO
from functools import wraps
import xml.etree.ElementTree as ET
from modules.user import login_required_json
from modules.admin import admin_required
from flask import jsonify, request, send_file, session, current_app

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_PATH, "database.db")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
IMAGE_DIR = "images"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def _guess_image_mimetype(extension):
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp"
    }.get(extension, "application/octet-stream")

def ftp_connect():
    """Connects to the FTP server and returns the FTP object."""
    try:
        ftp = ftplib.FTP(FTP_HOST)
        ftp.login(user=FTP_USER, passwd=FTP_PASS)
        return ftp
    except Exception as e:
        logger.error(f"FTP connection error: {e}")
        raise

def ensure_ftp_dir(ftp, dirname):
    try:
        ftp.cwd(dirname)
        ftp.cwd("..")
    except Exception:
        try:
            ftp.mkd(dirname)
        except Exception:
            pass

def save_image(file_data, extension):
    """Saves an image to the FTP server and returns its filename."""
    ftp = ftp_connect()
    ensure_ftp_dir(ftp, IMAGE_DIR)
    unique_filename = f"{uuid.uuid4().hex}.{extension}"
    file_stream = BytesIO(file_data)
    file_stream.seek(0)
    ftp.storbinary(f"STOR {IMAGE_DIR}/{unique_filename}", file_stream)
    ftp.quit()
    return unique_filename

def fetch_image(filename):
    """Fetches an image from the FTP server."""
    ftp = ftp_connect()
    file_data = BytesIO()
    ftp.retrbinary(f"RETR {IMAGE_DIR}/{filename}", file_data.write)
    ftp.quit()
    file_data.seek(0)
    return file_data

def save_report(record_id, file_data):
    """Saves a report file to the FTP server."""
    try:
        ftp = ftp_connect()
        unique_filename = f"{record_id}_{uuid.uuid4()}.pdf"
        file_stream = BytesIO(file_data)
        file_stream.seek(0)

        ftp.storbinary(f'STOR {unique_filename}', file_stream)
        ftp.quit()
        return unique_filename
    except Exception as e:
        logger.error(f"Error saving report for record {record_id}: {e}")
        raise

def delete_report(relative_path):
    """Deletes a report file from the FTP server."""
    try:
        ftp = ftp_connect()
        ftp.delete(relative_path)
        ftp.quit()
        logger.info(f"Deleted report file: {relative_path}")
    except Exception as e:
        logger.error(f"Error deleting report file {relative_path}: {e}")
        raise

def pentest_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in') or session.get('user_type') not in ('pentester', 'admin'):
            response = jsonify({"error": "Unauthorized access"})
            return response, 403
        return f(*args, **kwargs)
    return decorated_function

def get_pentest_data_internal(record_id=None):
    """Internal function to fetch pentest data (all records or a single record)."""
    default_pentest = {
        'report_file': None,
        'vulnerable': 0,
        'tested_by': None,
        'test_start_date': None,
        'test_end_date': None,
        'vulnerability_fixed': 0,
        'service_desk_link': None,
        'status': 'Not Started',
        'open_ports': "",
        'notes': "",
        'owasp_checklist': "",
        'vulnerabilities': ""
    }
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            if record_id is not None:
                c.execute("SELECT * FROM records WHERE id = ?", (record_id,))
                record_row = c.fetchone()
                if not record_row:
                    return None
                record = dict(record_row)

                c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
                pentest_row = c.fetchone()
                pentest = dict(pentest_row) if pentest_row else default_pentest

                return {
                    **pentest,
                    'recordId': record['id'],
                    'name': record['name'],
                    'ip_address': record['ip_address'],
                    'source': record['source'],
                    'description': record.get('description', '')
                }

            c.execute("SELECT * FROM records")
            rows = c.fetchall()
            dns_records = [dict(ix) for ix in rows]

            c.execute("SELECT * FROM pentest_data")
            pentest_records = {row['record_id']: dict(row) for row in c.fetchall()}

            return [
                {
                    **pentest_records.get(record['id'], default_pentest),
                    'recordId': record['id'],
                    'name': record['name'],
                    'ip_address': record['ip_address'],
                    'source': record['source'],
                    'description': record.get('description', '')
                } for record in dns_records
            ]

    except Exception as e:
        logger.error(f"Error fetching record details: {e}")
        return None

def get_record_details_internal(record_id):
    """Internal function to fetch record details."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM records WHERE id = ?", (record_id,))
            return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching record details for ID {record_id}: {e}")
        return None

def get_pentest_users_internal():
    """Fetches users with the 'pentest' role from the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            users = c.execute(
                "SELECT id, username FROM allowed_users WHERE role = 'pentester'"
            ).fetchall()
            return [{"id": user['id'], "username": user['username']} for user in users]
    except Exception as e:
        logger.error(f"Error fetching pentesters: {e}")
        return None

@login_required_json
@admin_required
def get_pentest_users():
    """GET /pentest_users: Get users with pentest role."""
    try:
        users = get_pentest_users_internal()
        return jsonify(users), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching pentest users: {e}")
        return jsonify({"message": "Error fetching pentest users"}), 500

def get_pentest_row(record_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
            return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching pentest data for ID {record_id}: {e}")
        return None

@login_required_json
@pentest_required
def create_or_update_pentest_data(record_id):
    """POST /pentest/<record_id>: Create or update pentest data."""
    record = get_record_details_internal(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM pentest_data")
        rows = c.fetchall()
        existing_data = [dict(ix) for ix in rows if ix['record_id'] == record_id]
        if len(existing_data) > 0:
            existing_data = existing_data[0]
        else:
            existing_data = {}
        
        admin = session['user_type'] == 'admin'

        data = {}
        for key in ['vulnerable', 'tested_by', 'test_start_date', 'test_end_date', 'vulnerability_fixed', 'service_desk_link', 'status', 'open_ports', 'notes', 'owasp_checklist', 'vulnerabilities', 'description']:
            if (value := request.form.get(key)) is not None:
                data[key] = value

        if not admin:
            if data.get('tested_by') != session['username']:
                return jsonify({"error": "Unauthorized to complete this action."}), 403
            
            if existing_data and existing_data.get('tested_by') not in [session['username'], 'Unassigned', None]:
                return jsonify({"error": "You are not allowed to change the data of another user's pentest."}), 403
            
        if data.get('status') not in ['Not Started', 'In Progress', 'Completed']:
            return jsonify({"error": "Invalid status. Please select from 'Not Started', 'In Progress', 'Completed."}), 400

        relative_path = existing_data.get('report_file')
        if 'report' in request.files:
            report_file = request.files['report']
            if report_file.filename != '' and report_file.filename.lower().endswith('.pdf'):
                try:
                    relative_path = save_report(record_id, report_file.read())
                    logger.debug(f"Saved report file: {relative_path}")
                except Exception as e:
                    return jsonify({"error": f"Failed to upload report: {e}"}), 500
            else:
                return jsonify({"error": "Invalid file. Please upload a PDF file."}), 400
            
        pentest_data = {
            'record_id': record_id,
            'dns_name': record['name'],
            'ip_address': record['ip_address'],
            'source': record['source'],
            'report_file': relative_path,
            'vulnerable': (
                0
                if data.get('vulnerable', existing_data.get('vulnerable', 0)) is None
                else int(data.get('vulnerable', existing_data.get('vulnerable', 0)))
            ),
            'tested_by': data.get('tested_by', existing_data.get('tested_by', '')),
            'test_start_date': data.get('test_start_date', existing_data.get('test_start_date', None)),
            'test_end_date': data.get('test_end_date', existing_data.get('test_end_date', None)),
            'vulnerability_fixed': (
                0
                if data.get('vulnerability_fixed', existing_data.get('vulnerability_fixed', 0)) is None
                else int(data.get('vulnerability_fixed', existing_data.get('vulnerability_fixed', 0)))
            ),
            'service_desk_link': data.get('service_desk_link', existing_data.get('service_desk_link', '')),
            'status': data.get('status', existing_data.get('status', 'Not Started')),
            'open_ports': data.get('open_ports', existing_data.get('open_ports', "")),
            'notes': data.get('notes', existing_data.get('notes', "")),
            'owasp_checklist': data.get('owasp_checklist', existing_data.get('owasp_checklist', "")),
            'vulnerabilities': data.get('vulnerabilities', existing_data.get('vulnerabilities', ""))
        }

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            if existing_data:
                filtered_pentest_data = {k: v for k, v in pentest_data.items() if v is not None}
                if filtered_pentest_data:
                    update_query = "UPDATE pentest_data SET " + ", ".join([f"{key} = ?" for key in filtered_pentest_data.keys()]) + " WHERE record_id = ?"
                    c.execute(update_query, list(filtered_pentest_data.values()) + [record_id])
            else:
                c.execute("""
                    INSERT INTO pentest_data (record_id, dns_name, ip_address, source, report_file, vulnerable,
                                             tested_by, test_start_date, test_end_date, vulnerability_fixed, service_desk_link, status,
                                             open_ports, notes, owasp_checklist, vulnerabilities)
                    VALUES (:record_id, :dns_name, :ip_address, :source, :report_file, :vulnerable,
                                             :tested_by, :test_start_date, :test_end_date, :vulnerability_fixed, :service_desk_link, :status,
                                             :open_ports, :notes, :owasp_checklist, :vulnerabilities)
                """, pentest_data)

            # Sync description back to records table if provided
            if 'description' in data:
                c.execute("""
                    UPDATE records
                    SET description = ?,
                        last_modification_date = datetime('now', '+4 hours')
                    WHERE id = ?
                """, (data.get('description', ''), record_id))

            conn.commit()

        return jsonify({"message": "Pentest data updated successfully."}), 200

    except Exception as e:
        logger.error(f"Error creating/updating pentest data for record {record_id}: {e}")
        return jsonify({"error": str(e)}), 500

@login_required_json
@pentest_required
def upload_pentest_image(record_id):
    """POST /pentest/<record_id>/images: Upload image for pentest notes/vulns."""
    record = get_record_details_internal(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    pentest_row = get_pentest_row(record_id)
    admin = session.get('user_type') == 'admin'
    if not admin:
        if not pentest_row or pentest_row['tested_by'] != session.get('username'):
            return jsonify({"error": "Unauthorized to upload images for this record."}), 403

    if 'image' not in request.files:
        return jsonify({"error": "Image file is required."}), 400
    image = request.files['image']
    if image.filename == '':
        return jsonify({"error": "Image file is required."}), 400

    extension = image.filename.rsplit('.', 1)[-1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": "Unsupported image type."}), 400

    try:
        filename = save_image(image.read(), extension)
        return jsonify({"url": f"/pentest/images/{filename}"}), 200
    except Exception as e:
        logger.error(f"Error uploading image for record {record_id}: {e}")
        return jsonify({"error": "Failed to upload image."}), 500

@login_required_json
@pentest_required
def get_pentest_image(filename):
    """GET /pentest/images/<filename>: Serve image by filename."""
    if not re.match(r'^[a-f0-9]{32}\.(png|jpg|jpeg|gif|webp)$', filename):
        return jsonify({"error": "Invalid filename."}), 400

    extension = filename.rsplit('.', 1)[-1].lower()
    try:
        file_data = fetch_image(filename)
        return send_file(file_data, mimetype=_guess_image_mimetype(extension))
    except Exception as e:
        logger.error(f"Error fetching image {filename}: {e}")
        return jsonify({"error": "Image not found."}), 404

@login_required_json
@pentest_required
def get_pentest_data():
    """GET /pentest/records: Retrieve pentest data."""
    data = get_pentest_data_internal()
    if data:
        response = jsonify(data)
        status_code = 200
    else:
        response = jsonify({"error": "Pentest data not found"})
        status_code = 404

    return response, status_code


@login_required_json
@admin_required
def delete_pentest_data(record_id):
    """DELETE /pentest/<record_id>: Delete pentest data and report."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT report_file FROM pentest_data WHERE record_id = ?", (record_id,))
            result = c.fetchone()

            if result:
                if report_file := result[0]:
                    try:
                        delete_report(report_file)
                    except Exception as e:
                        return jsonify({"error": f"Failed to delete report: {e}"}), 500
                c.execute("DELETE FROM pentest_data WHERE record_id = ?", (record_id,))
                conn.commit()
                return jsonify({"message": "Pentest data deleted successfully."}), 200
            else:
                return jsonify({"error": "Pentest data not found"}), 404
    except Exception as e:
        logger.error(f"Error deleting pentest data for record {record_id}: {e}")
        return jsonify({"error": str(e)}), 500

@login_required_json
@pentest_required
def get_report(record_id):
    """GET /pentest/<record_id>/report: Serve the PDF report."""
    pentest_data = get_pentest_data_internal(record_id)
    if not pentest_data or not pentest_data['report_file']:
        return jsonify({"error": "Pentest data or report file not found"}), 404

    try:
        ftp = ftp_connect()
        file_data = BytesIO()
        ftp.retrbinary(f'RETR {pentest_data["report_file"]}', file_data.write)
        ftp.quit()
        file_data.seek(0)
        return send_file(file_data, mimetype='application/pdf', as_attachment=True, download_name=f"report_{record_id}.pdf")
    except Exception as e:
        logger.error(f"Error retrieving report for record {record_id}: {e}")
        return jsonify({"error": str(e)}), 500

@login_required_json
@pentest_required
def delete_report_route(record_id):
    """DELETE /pentest/<record_id>/report: Deletes report file."""
    pentest_data = get_pentest_data_internal(record_id)
    if not pentest_data or not pentest_data['report_file']:
        return jsonify({"error": "Pentest data or report file not found"}), 404

    try:
        delete_report(pentest_data["report_file"])
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE pentest_data SET report_file = NULL WHERE record_id = ?", (record_id,))
            if c.rowcount == 0:
                return jsonify({"error": f"Pentest data not found for record {record_id}"}), 404
            conn.commit()
        return jsonify({"message": "Report Deleted"}), 200
    except Exception as e:
        return jsonify({"error": f"Error deleting report: {e}"}), 500
