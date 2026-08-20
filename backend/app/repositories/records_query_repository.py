from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.domain.dashboard import build_findings_summary
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection, get_table_columns
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


def _table_columns(cursor: Any, table_name: str) -> set:
    try:
        return get_table_columns(cursor, table_name)
    except Exception:
        return set()


def _fetch_findings_rows(cursor: Any) -> List[Dict[str, Any]]:
    columns = _table_columns(cursor, "pentest_findings")
    if not columns:
        return []
    title_sql = (
        "COALESCE(f.title, f.category_name, '') AS title"
        if "title" in columns
        else "COALESCE(f.category_name, '') AS title"
    )
    app_sql = "f.application_id" if "application_id" in columns else "NULL AS application_id"
    cursor.execute(
        f"""
        SELECT
            f.id,
            {title_sql},
            COALESCE(f.status, 'open') AS status,
            COALESCE(f.base_score, 0) AS base_score,
            {app_sql},
            f.created_at,
            f.updated_at
        FROM pentest_findings f
        WHERE COALESCE(f.status, 'open') <> 'draft'
        """
    )
    return rows_to_dicts(cursor.fetchall())


def _fetch_dashboard_applications(cursor: Any) -> List[Dict[str, Any]]:
    if not _table_columns(cursor, "applications"):
        return []
    record_cols = _table_columns(cursor, "records")
    if "application_id" not in record_cols:
        cursor.execute("SELECT a.id, a.name FROM applications a ORDER BY a.name")
        rows = rows_to_dicts(cursor.fetchall())
        for row in rows:
            row["open_finding_count"] = 0
            row["in_scope_count"] = 0
            row["started_count"] = 0
        return rows
    finding_cols = _table_columns(cursor, "pentest_findings")
    has_in_scope = "in_scope" in record_cols
    has_finding_app = "application_id" in finding_cols
    finding_join = "LEFT JOIN pentest_findings f ON f.application_id = a.id" if has_finding_app else ""
    finding_count_sql = (
        "COUNT(DISTINCT f.id) FILTER (WHERE COALESCE(f.status, 'open') IN ('open', 'retest')) AS open_finding_count"
        if has_finding_app
        else "0 AS open_finding_count"
    )
    in_scope_pred = "COALESCE(r.in_scope, FALSE)" if has_in_scope else "TRUE"
    missing_pred = "COALESCE(r.status, '') <> 'missing'"
    cursor.execute(
        f"""
        SELECT
            a.id,
            a.name,
            COUNT(DISTINCT r.id) FILTER (
                WHERE {in_scope_pred} AND {missing_pred}
            ) AS in_scope_count,
            COUNT(DISTINCT r.id) FILTER (
                WHERE {in_scope_pred}
                  AND {missing_pred}
                  AND COALESCE(p.status, 'Not Started') IN ('In Progress', 'Completed')
            ) AS started_count,
            {finding_count_sql}
        FROM applications a
        LEFT JOIN records r ON r.application_id = a.id
        LEFT JOIN pentest_data p ON p.record_id = r.id
        {finding_join}
        GROUP BY a.id
        ORDER BY open_finding_count DESC, a.name
        """
    )
    rows = rows_to_dicts(cursor.fetchall())
    for row in rows:
        row["open_finding_count"] = int(row.get("open_finding_count") or 0)
        row["in_scope_count"] = int(row.get("in_scope_count") or 0)
        row["started_count"] = int(row.get("started_count") or 0)
    return rows


def fetch_dashboard_data(db_path: str = DB_PATH) -> Dict[str, Any]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        record_cols = _table_columns(c, "records")
        app_col = "r.application_id" if "application_id" in record_cols else "NULL"

        c.execute(
            f"""
            SELECT
                r.id,
                r.name,
                r.source,
                r.status,
                r.origin,
                r.sync_conflict,
                r.last_modification_date,
                {app_col} AS application_id
            FROM records r
            """
        )
        records = rows_to_dicts(c.fetchall())

        finding_count_sql = (
            "COALESCE((SELECT COUNT(*) FROM pentest_findings f WHERE f.record_id = r.id), 0)"
            if _table_columns(c, "pentest_findings")
            else "0"
        )
        c.execute(
            f"""
            SELECT
                r.id AS recordId,
                r.name,
                r.source,
                {app_col} AS applicationId,
                COALESCE(p.status, 'Not Started') AS status,
                COALESCE(p.vulnerable, 0) AS vulnerable,
                COALESCE(p.vulnerability_fixed, 0) AS vulnerability_fixed,
                {finding_count_sql} AS finding_count,
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

        findings_rows = _fetch_findings_rows(c)
        applications = _fetch_dashboard_applications(c)

    return {
        "records": records,
        "pentestRecords": pentest_records,
        "ipSources": ip_sources,
        "findingsSummary": build_findings_summary(findings_rows),
        "applications": applications,
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
