from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection, get_table_columns

ENV_TEMPLATES = (
    ("unassigned", "Unassigned", False, False),
    ("prod", "Production", True, True),
    ("stg", "Staging", False, False),
    ("pp", "Preprod", False, False),
    ("qa", "QA", False, False),
)

_STG_MARKERS = ("-stg", ".stg.", "staging")
_QA_MARKERS = ("-qa", ".qa.", "-uat", ".uat.")
_PP_MARKERS = ("-pp", ".pp.", "preprod", "pre-prod")


def suggest_env_slug(fqdn: str) -> str:
    name = str(fqdn or "").strip().lower()
    if any(marker in name for marker in _STG_MARKERS):
        return "stg"
    if any(marker in name for marker in _QA_MARKERS):
        return "qa"
    if any(marker in name for marker in _PP_MARKERS):
        return "pp"
    return ""


def _insert_env_if_missing(
    cursor: Any,
    application_id: int,
    slug: str,
    display_name: str,
    is_production: bool,
    include_in_exec_report: bool,
) -> None:
    cursor.execute(
        """
        INSERT INTO environments (
            application_id, slug, display_name, is_production, include_in_exec_report
        )
        SELECT ?, ?, ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM environments WHERE application_id = ? AND slug = ?
        )
        """,
        (
            application_id,
            slug,
            display_name,
            1 if is_production else 0,
            1 if include_in_exec_report else 0,
            application_id,
            slug,
        ),
    )


def seed_environments_for_app(cursor: Any, application_id: int) -> None:
    cursor.execute(
        "SELECT COUNT(*) AS n FROM environments WHERE application_id = ?",
        (application_id,),
    )
    row = cursor.fetchone()
    count = int(row["n"] if isinstance(row, dict) else row[0] or 0)
    if count:
        return
    for slug, display_name, is_production, include_in_exec_report in ENV_TEMPLATES:
        _insert_env_if_missing(
            cursor,
            application_id,
            slug,
            display_name,
            is_production,
            include_in_exec_report,
        )


def ensure_unassigned_environment(cursor: Any, application_id: int) -> Optional[int]:
    existing = fetch_unassigned_id(cursor, application_id)
    if existing:
        return existing
    slug, display_name, is_production, include_in_exec_report = ENV_TEMPLATES[0]
    _insert_env_if_missing(
        cursor,
        application_id,
        slug,
        display_name,
        is_production,
        include_in_exec_report,
    )
    return fetch_unassigned_id(cursor, application_id)


def fetch_unassigned_id(cursor: Any, application_id: int) -> Optional[int]:
    cursor.execute(
        "SELECT id FROM environments WHERE application_id = ? AND slug = 'unassigned'",
        (application_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return int(row["id"])
    return int(row[0])


def fetch_environments(application_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        seed_environments_for_app(c, application_id)
        conn.commit()
        extra_cols = get_table_columns(c, "environments")
        scan_col = ", e.max_concurrent_scans" if "max_concurrent_scans" in extra_cols else ""
        c.execute(
            f"""
            SELECT
                e.id,
                e.application_id,
                e.slug,
                e.display_name,
                e.is_production,
                e.include_in_exec_report,
                e.allow_destructive
                {scan_col},
                e.roe_text,
                e.contacts,
                e.data_class,
                e.in_scope_urls,
                e.out_of_scope_urls,
                e.creds_vault_pointer,
                e.test_window,
                COUNT(r.id) FILTER (WHERE r.id IS NOT NULL) AS host_count,
                COUNT(r.id) FILTER (
                    WHERE COALESCE(r.in_scope, FALSE)
                      AND COALESCE(r.status, '') <> 'missing'
                ) AS in_scope_count
            FROM environments e
            LEFT JOIN records r ON r.environment_id = e.id
            WHERE e.application_id = ?
            GROUP BY e.id
            ORDER BY
                CASE e.slug
                    WHEN 'prod' THEN 0
                    WHEN 'stg' THEN 1
                    WHEN 'pp' THEN 2
                    WHEN 'qa' THEN 3
                    WHEN 'unassigned' THEN 4
                    ELSE 5
                END,
                e.display_name
            """,
            (application_id,),
        )
        return [dict(row) for row in c.fetchall()]


def fetch_environment(application_id: int, env_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            """
            SELECT *
            FROM environments
            WHERE application_id = ? AND id = ?
            """,
            (application_id, env_id),
        )
        row = c.fetchone()
    return dict(row) if row else None


def update_environment(application_id: int, env_id: int, fields: Dict[str, Any], db_path: str = DB_PATH) -> bool:
    allowed = {
        "display_name",
        "include_in_exec_report",
        "allow_destructive",
        "max_concurrent_scans",
        "roe_text",
        "contacts",
        "data_class",
        "in_scope_urls",
        "out_of_scope_urls",
        "creds_vault_pointer",
        "test_window",
    }
    assignments = []
    values: List[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        assignments.append(f"{key} = ?")
        if key in {"include_in_exec_report", "allow_destructive"}:
            values.append(1 if value else 0)
        elif key == "max_concurrent_scans":
            values.append(int(value))
        else:
            values.append("" if value is None else str(value))
    if not assignments:
        return fetch_environment(application_id, env_id, db_path=db_path) is not None
    values.extend([application_id, env_id])
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            f"""
            UPDATE environments
            SET {", ".join(assignments)}
            WHERE application_id = ? AND id = ?
            """,
            tuple(values),
        )
        updated = c.rowcount > 0
        conn.commit()
    return updated


def create_environment(application_id: int, fields: Dict[str, Any], db_path: str = DB_PATH) -> Dict[str, Any]:
    slug = str(fields.get("slug") or "").strip().lower()
    display_name = str(fields.get("display_name") or "").strip()
    if not slug or not display_name:
        raise ValueError("slug_and_display_name_required")
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        seed_environments_for_app(c, application_id)
        c.execute(
            """
            INSERT INTO environments (
                application_id, slug, display_name, is_production, include_in_exec_report
            )
            VALUES (?, ?, ?, ?, ?)
            RETURNING *
            """,
            (
                application_id,
                slug,
                display_name,
                1 if fields.get("is_production") else 0,
                1 if fields.get("include_in_exec_report") else 0,
            ),
        )
        row = c.fetchone()
        conn.commit()
    return dict(row)


def delete_environment(application_id: int, env_id: int, db_path: str = DB_PATH) -> str:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            "SELECT id, slug FROM environments WHERE application_id = ? AND id = ?",
            (application_id, env_id),
        )
        env = c.fetchone()
        if not env:
            return "not_found"
        slug = str(env["slug"] if isinstance(env, dict) else env[1])
        if slug == "unassigned":
            return "protected"
        record_columns = get_table_columns(c, "records")
        occurrence_columns = get_table_columns(c, "finding_occurrences")
        if "in_scope" in record_columns or occurrence_columns:
            occurrence_sql = (
                "OR EXISTS (SELECT 1 FROM finding_occurrences o WHERE o.record_id = records.id)"
                if occurrence_columns
                else ""
            )
            finding_sql = "OR EXISTS (SELECT 1 FROM pentest_findings f WHERE f.record_id = records.id)"
            c.execute(
                f"""
                SELECT COUNT(*) AS n FROM records
                WHERE environment_id = ? AND (
                    COALESCE(in_scope, FALSE)
                    {finding_sql}
                    {occurrence_sql}
                )
                """,
                (env_id,),
            )
            row = c.fetchone()
            count = int(row["n"] if isinstance(row, dict) else row[0] or 0)
            if count:
                return "in_use"
        export_cols = get_table_columns(c, "report_exports")
        if export_cols:
            c.execute(
                "SELECT COUNT(*) AS n FROM report_exports WHERE scope_kind = 'environment' AND scope_id = ?",
                (env_id,),
            )
            row = c.fetchone()
            if int(row["n"] if isinstance(row, dict) else row[0] or 0):
                return "in_use"
        c.execute(
            "UPDATE records SET environment_id = NULL WHERE environment_id = ?",
            (env_id,),
        )
        c.execute(
            "DELETE FROM environments WHERE application_id = ? AND id = ?",
            (application_id, env_id),
        )
        conn.commit()
    return "ok"
