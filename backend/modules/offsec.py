import os
import uuid
import ftplib
import sqlite3
import logging
from io import BytesIO
from functools import wraps
import xml.etree.ElementTree as ET
from modules.user import login_required_json
from flask import jsonify, request, send_file, session

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DATA_PATH") + "database.db"
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")

def ftp_connect():
    """Connects to the FTP server and returns the FTP object."""
    try:
        ftp = ftplib.FTP(FTP_HOST)
        ftp.login(user=FTP_USER, passwd=FTP_PASS)
        return ftp
    except Exception as e:
        logger.error(f"FTP connection error: {e}")
        raise

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

def get_pentest_data_internal(record_id):
    """Internal function to retrieve pentest data for a record ID."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM pentest_data WHERE record_id = ?", (record_id,))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving pentest data for record {record_id}: {e}")
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

@login_required_json
@pentest_required
def create_or_update_pentest_data(record_id):
    """POST /pentest/<record_id>: Create or update pentest data."""
    record = get_record_details_internal(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    try:
        existing_data = get_pentest_data_internal(record_id) or {}
        data = {}
        for key in ['vulnerable', 'tested_by', 'test_start_date', 'test_end_date', 'vulnerability_fixed', 'service_desk_link', 'status']:
            if (value := request.form.get(key)) is not None:
                data[key] = value

        relative_path = existing_data.get('report_file')
        if 'report' in request.files:
            report_file = request.files['report']
            if report_file.filename != '' and report_file.filename.lower().endswith('.pdf'):
                try:
                    relative_path = save_report(record_id, report_file.read())
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
            'status': data.get('status', existing_data.get('status', 'Not Started'))
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
                                             tested_by, test_start_date, test_end_date, vulnerability_fixed, service_desk_link, status)
                    VALUES (:record_id, :dns_name, :ip_address, :source, :report_file, :vulnerable,
                            :tested_by, :test_start_date, :test_end_date, :vulnerability_fixed, :service_desk_link, :status)
                """, pentest_data)
            conn.commit()

        return jsonify({"message": "Pentest data updated successfully."}), 200

    except Exception as e:
        logger.error(f"Error creating/updating pentest data for record {record_id}: {e}")
        return jsonify({"error": str(e)}), 500

@login_required_json
@pentest_required
def get_pentest_data(record_id):
    """GET /pentest/<record_id>: Retrieve pentest data."""
    data = get_pentest_data_internal(record_id)
    if data:
        response = jsonify(data)
        status_code = 200
    else:
        response = jsonify({"error": "Pentest data not found"})
        status_code = 404

    return response, status_code

@login_required_json
@pentest_required
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
