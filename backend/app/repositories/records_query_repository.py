from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.repositories.records_row_mapper import (
    RECORD_WITH_PENTEST_AND_APP_SELECT,
    rows_to_dicts,
)


def determine_source(ip: str, db_path: str = DB_PATH) -> str:
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("SELECT source_name FROM ip_sources WHERE ip_address = ?", (ip,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "Other"


def fetch_dashboard_data(db_path: str = DB_PATH) -> Dict[str, List[Dict[str, Any]]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()

        c.execute(
            """
            SELECT
                r.id,
                r.name,
                r.source,
                r.status,
                r.origin,
                r.sync_conflict,
                r.last_modification_date
            FROM records r
            """
        )
        records = rows_to_dicts(c.fetchall())

        c.execute(
            """
            SELECT
                r.id AS recordId,
                r.name,
                r.source,
                COALESCE(p.status, 'Not Started') AS status,
                COALESCE(p.vulnerable, 0) AS vulnerable,
                COALESCE(p.vulnerability_fixed, 0) AS vulnerability_fixed,
                COALESCE(p.vulnerabilities, '') AS vulnerabilities,
                p.tested_by,
                p.test_start_date,
                p.test_end_date
            FROM records r
            LEFT JOIN pentest_data p ON r.id = p.record_id
            """
        )
        pentest_records = rows_to_dicts(c.fetchall())

        c.execute("SELECT source_name FROM ip_sources")
        ip_sources = rows_to_dicts(c.fetchall())

    return {
        "records": records,
        "pentestRecords": pentest_records,
        "ipSources": ip_sources,
    }


def fetch_records(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute(RECORD_WITH_PENTEST_AND_APP_SELECT)
    rows = c.fetchall()
    conn.close()
    return rows_to_dicts(rows)


def fetch_record_history(record_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute("SELECT * FROM record_history WHERE record_id = ? ORDER BY timestamp DESC", (record_id,))
    rows = c.fetchall()
    conn.close()
    return rows_to_dicts(rows)


def fetch_record_by_id(record_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute(RECORD_WITH_PENTEST_AND_APP_SELECT + " WHERE r.id = ?", (record_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def fetch_record_by_domain(domain: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute(
        """
        SELECT
            r.id,
            r.name,
            r.ip_address,
            r.source,
            r.status,
            r.origin,
            r.sync_conflict,
            r.sync_conflict_reason,
            r.creation_date,
            r.last_modification_date,
            r.application_owner,
            r.maintainer,
            r.description,
            r.application_id,
            p.open_ports,
            a.name AS application_name
        FROM records r
        LEFT JOIN pentest_data p ON r.id = p.record_id
        LEFT JOIN applications a ON r.application_id = a.id
        WHERE r.name = ?
        """,
        (domain,),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


__all__ = [
    "determine_source",
    "fetch_dashboard_data",
    "fetch_record_by_domain",
    "fetch_record_by_id",
    "fetch_record_history",
    "fetch_records",
]
