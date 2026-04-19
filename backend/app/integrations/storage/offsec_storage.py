import ftplib
import json
import logging
import os
import re
import uuid
from io import BytesIO

from flask import session

from app.domain.offsec.shared import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.services.authorization_service import user_has_permission

logger = logging.getLogger(__name__)

FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
IMAGE_DIR = "images"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
IMAGE_FILENAME_PATTERN = r"[a-f0-9]{32}\.(?:png|jpg|jpeg|gif|webp)"
IMAGE_REFERENCE_PATTERN = re.compile(
    rf"(?:https?://[^)\s]+)?/pentest/images/({IMAGE_FILENAME_PATTERN})",
    re.IGNORECASE,
)


def guess_image_mimetype(extension):
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
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


def delete_image(filename):
    """Deletes an uploaded pentest image from FTP storage."""
    ftp = ftp_connect()
    ftp.delete(f"{IMAGE_DIR}/{filename}")
    ftp.quit()


def extract_image_filenames(raw_value):
    text = str(raw_value or "")
    return {match.lower() for match in IMAGE_REFERENCE_PATTERN.findall(text)}


def extract_image_filenames_from_vulnerabilities(raw_value):
    filenames = set()
    parsed = []

    if isinstance(raw_value, list):
        parsed = raw_value
    elif isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
        except Exception:
            parsed = []

    if not isinstance(parsed, list):
        return filenames

    for vulnerability in parsed:
        if not isinstance(vulnerability, dict):
            continue
        filenames.update(extract_image_filenames(vulnerability.get("description", "")))
    return filenames


def collect_referenced_image_filenames(description, notes, vulnerabilities):
    filenames = set()
    filenames.update(extract_image_filenames(description))
    filenames.update(extract_image_filenames(notes))
    filenames.update(extract_image_filenames_from_vulnerabilities(vulnerabilities))
    return filenames


def is_image_referenced_anywhere(filename):
    like_value = f"%{filename}%"
    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT 1 FROM records WHERE description LIKE ? LIMIT 1", (like_value,))
        if c.fetchone():
            return True

        c.execute(
            """
            SELECT 1
            FROM pentest_data
            WHERE notes LIKE ? OR vulnerabilities LIKE ?
            LIMIT 1
            """,
            (like_value, like_value),
        )
        return c.fetchone() is not None


def cleanup_unreferenced_images(filenames):
    for filename in sorted(set(filenames)):
        if is_image_referenced_anywhere(filename):
            continue
        try:
            delete_image(filename)
            logger.info(f"Deleted unreferenced image from FTP: {filename}")
        except Exception as e:
            logger.warning(f"Failed to delete unreferenced image '{filename}': {e}")


def can_user_access_image(filename):
    username = session.get("username")
    role = session.get("user_type")
    if user_has_permission(username, role, "modify_others_pentests_admin"):
        return True
    if not username:
        return False

    like_value = f"%{filename}%"
    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT
                p.record_id,
                p.tested_by,
                p.notes,
                p.vulnerabilities,
                r.description,
                CASE WHEN pc.username IS NULL THEN 0 ELSE 1 END AS is_collaborator
            FROM pentest_data p
            JOIN records r ON r.id = p.record_id
            LEFT JOIN pentest_collaborators pc
              ON pc.record_id = p.record_id
             AND pc.username = ?
            WHERE p.tested_by = ?
               OR pc.username = ?
            """,
            (username, username, username),
        )
        rows = c.fetchall()

    for row in rows:
        description = str(row.get("description") or "")
        notes = str(row.get("notes") or "")
        if filename in description or filename in notes:
            return True

        vulnerabilities = []
        raw_vulnerabilities = row.get("vulnerabilities")
        if isinstance(raw_vulnerabilities, str) and raw_vulnerabilities.strip():
            try:
                vulnerabilities = json.loads(raw_vulnerabilities)
            except Exception:
                vulnerabilities = []
        elif isinstance(raw_vulnerabilities, list):
            vulnerabilities = raw_vulnerabilities

        if not isinstance(vulnerabilities, list):
            vulnerabilities = []

        if not row.get("is_collaborator"):
            if any(filename in str(vulnerability.get("description") or "") for vulnerability in vulnerabilities):
                return True
            continue

        owner = str(row.get("tested_by") or "").strip()
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                continue
            vulnerability_owner = str(vulnerability.get("created_by") or owner).strip()
            if vulnerability_owner == str(username).strip() and filename in str(vulnerability.get("description") or ""):
                return True

    return False


def save_report(record_id, file_data):
    """Saves a report file to the FTP server."""
    try:
        ftp = ftp_connect()
        unique_filename = f"{record_id}_{uuid.uuid4()}.pdf"
        file_stream = BytesIO(file_data)
        file_stream.seek(0)

        ftp.storbinary(f"STOR {unique_filename}", file_stream)
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


__all__ = [
    "ALLOWED_IMAGE_EXTENSIONS",
    "can_user_access_image",
    "cleanup_unreferenced_images",
    "collect_referenced_image_filenames",
    "delete_report",
    "fetch_image",
    "ftp_connect",
    "guess_image_mimetype",
    "save_image",
    "save_report",
]
