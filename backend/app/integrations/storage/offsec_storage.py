import ftplib
import json
import logging
import os
import re
import sqlite3
import uuid
from io import BytesIO

from flask import session

from app.domain.offsec.shared import DB_PATH
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT 1
            FROM pentest_data
            WHERE tested_by = ?
              AND (notes LIKE ? OR vulnerabilities LIKE ?)
            LIMIT 1
            """,
            (username, like_value, like_value),
        )
        if c.fetchone():
            return True

        c.execute(
            """
            SELECT 1
            FROM records r
            JOIN pentest_data p ON p.record_id = r.id
            WHERE p.tested_by = ?
              AND r.description LIKE ?
            LIMIT 1
            """,
            (username, like_value),
        )
        return c.fetchone() is not None


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
