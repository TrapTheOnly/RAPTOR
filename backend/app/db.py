import os
import sqlite3
import logging
from .config import DB_PATH

logger = logging.getLogger(__name__)


def init_db(db_path: str = DB_PATH):
    """
    Create the tables for records, allowed users, ip sources, record history,
    pentest data, and system status if they do not exist.
    """
    logger.info("Initializing database...")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

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
            last_modification_date TEXT,
            application_owner TEXT DEFAULT '',
            maintainer TEXT DEFAULT '',
            description TEXT DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS allowed_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            added_date TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ip_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            ip_address TEXT NOT NULL UNIQUE
        )
    """)

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

    c.execute("""
        CREATE TABLE IF NOT EXISTS system_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            message TEXT,
            details TEXT,
            last_updated TEXT NOT NULL
        )
    """)

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS pentest_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            tested_by TEXT,
            vulnerable INTEGER,
            vulnerability_fixed INTEGER,
            status TEXT,
            notes TEXT,
            test_start_date TEXT,
            test_end_date TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
        """
    )

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")
