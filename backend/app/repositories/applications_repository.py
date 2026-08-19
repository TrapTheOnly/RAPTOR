from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection, get_table_columns
from app.repositories.environments_repository import (
    fetch_unassigned_id,
    seed_environments_for_app,
)

APP_FIELD_COLUMNS = (
    "owner",
    "data_class",
    "roe_link",
    "cookie_domain",
    "idp",
    "token_audience",
    "app_lead",
)


def fetch_applications(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        columns = get_table_columns(c, "applications")
        extra = [col for col in APP_FIELD_COLUMNS if col in columns]
        extra_sql = "".join(f", a.{col}" for col in extra)
        has_envs = "environment_id" in get_table_columns(c, "records")
        has_finding_app = "application_id" in get_table_columns(c, "pentest_findings")
        finding_join = "LEFT JOIN pentest_findings f ON f.application_id = a.id" if has_finding_app else ""
        finding_count_sql = (
            "COUNT(DISTINCT f.id) FILTER (WHERE COALESCE(f.status, 'open') IN ('open', 'draft')) AS open_finding_count"
            if has_finding_app
            else "0 AS open_finding_count"
        )
        if has_envs:
            c.execute(
                f"""
                SELECT
                    a.id,
                    a.name,
                    a.created_by,
                    a.created_at
                    {extra_sql},
                    COUNT(DISTINCT r.id) AS host_count,
                    COUNT(DISTINCT r.id) FILTER (
                        WHERE COALESCE(r.in_scope, FALSE)
                          AND COALESCE(r.status, '') <> 'missing'
                          AND COALESCE(e.slug, '') <> 'unassigned'
                    ) AS in_scope_count,
                    COUNT(DISTINCT r.id) FILTER (
                        WHERE COALESCE(r.in_scope, FALSE)
                          AND COALESCE(p.status, 'Not Started') IN ('In Progress', 'Completed')
                          AND COALESCE(e.slug, '') <> 'unassigned'
                          AND COALESCE(r.status, '') <> 'missing'
                    ) AS started_count,
                    {finding_count_sql},
                    COUNT(DISTINCT r.id) FILTER (
                        WHERE COALESCE(e.slug, '') = 'unassigned'
                          AND COALESCE(r.in_scope, FALSE)
                    ) AS unassigned_in_scope_count
                FROM applications a
                LEFT JOIN records r ON r.application_id = a.id
                LEFT JOIN environments e ON e.id = r.environment_id
                LEFT JOIN pentest_data p ON p.record_id = r.id
                {finding_join}
                GROUP BY a.id
                ORDER BY a.name
                """
            )
        else:
            c.execute(
                f"""
                SELECT a.id, a.name, a.created_by, a.created_at {extra_sql}
                FROM applications a
                ORDER BY a.name
                """
            )
        rows = c.fetchall()
    apps = [dict(ix) for ix in rows]
    if has_envs and apps:
        with get_db_connection(db_path) as conn:
            conn.row_factory = ROW_AS_DICT
            c = conn.cursor()
            c.execute(
                """
                SELECT
                    e.application_id,
                    e.id,
                    e.slug,
                    e.display_name,
                    COUNT(r.id) FILTER (
                        WHERE COALESCE(r.in_scope, FALSE)
                          AND COALESCE(r.status, '') <> 'missing'
                    ) AS in_scope_count,
                    COUNT(r.id) FILTER (
                        WHERE COALESCE(r.in_scope, FALSE)
                          AND COALESCE(r.status, '') <> 'missing'
                          AND COALESCE(p.status, 'Not Started') IN ('In Progress', 'Completed')
                    ) AS started_count
                FROM environments e
                LEFT JOIN records r ON r.environment_id = e.id
                LEFT JOIN pentest_data p ON p.record_id = r.id
                GROUP BY e.id
                ORDER BY e.application_id, e.slug
                """
            )
            by_app: Dict[int, List[Dict[str, Any]]] = {}
            for row in c.fetchall() or []:
                item = dict(row)
                by_app.setdefault(int(item["application_id"]), []).append(item)
        for app in apps:
            app["environments"] = by_app.get(int(app["id"]), [])
    return apps


def fetch_application(app_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    apps = fetch_applications(db_path=db_path)
    for app in apps:
        if int(app.get("id") or 0) == int(app_id):
            return app
    return None


def create_application(name: str, created_by: str, db_path: str = DB_PATH) -> Optional[int]:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO applications (name, created_by, created_at)
            VALUES (?, ?, (NOW() + INTERVAL '4 hours'))
            RETURNING id
            """,
            (name, created_by),
        )
        row = c.fetchone()
        app_id = int(row[0] if not isinstance(row, dict) else row["id"])
        seed_environments_for_app(c, app_id)
        conn.commit()
    return app_id


def update_application(
    app_id: int,
    name: str,
    db_path: str = DB_PATH,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> bool:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute("SELECT id, name FROM applications WHERE id = ?", (app_id,))
        existing_app = c.fetchone()
        if not existing_app:
            return False

        old_name = str(existing_app["name"] or "").strip()
        assignments = ["name = ?"]
        values: List[Any] = [name]
        app_columns = get_table_columns(c, "applications")
        for key, value in (extra_fields or {}).items():
            if key in APP_FIELD_COLUMNS and key in app_columns:
                assignments.append(f"{key} = ?")
                values.append("" if value is None else str(value))
        values.append(app_id)
        c.execute(
            f"UPDATE applications SET {', '.join(assignments)} WHERE id = ?",
            tuple(values),
        )

        record_columns = get_table_columns(c, "records")
        if "application_name" in record_columns:
            c.execute(
                """
                UPDATE records
                SET application_id = ?
                WHERE (application_id IS NULL OR application_id = 0)
                  AND application_name = ?
                """,
                (app_id, old_name),
            )
            c.execute(
                """
                UPDATE records
                SET application_name = ?
                WHERE application_id = ?
                   OR application_name = ?
                """,
                (name, app_id, old_name),
            )

        conn.commit()
    return True


def delete_application(app_id: int, db_path: str = DB_PATH) -> str:
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM applications WHERE id = ?", (app_id,))
        if not c.fetchone():
            return "not_found"

        record_columns = get_table_columns(c, "records")
        if "in_scope" in record_columns:
            c.execute(
                """
                SELECT COUNT(*) AS n FROM records
                WHERE application_id = ? AND COALESCE(in_scope, FALSE)
                """,
                (app_id,),
            )
            in_scope_count = c.fetchone()
            count = int(in_scope_count[0] if not isinstance(in_scope_count, dict) else in_scope_count["n"])
            if count:
                return "in_use"

        finding_columns = get_table_columns(c, "pentest_findings")
        if "application_id" in finding_columns:
            c.execute(
                "SELECT COUNT(*) AS n FROM pentest_findings WHERE application_id = ?",
                (app_id,),
            )
            finding_row = c.fetchone()
            finding_count = int(finding_row[0] if not isinstance(finding_row, dict) else finding_row["n"])
            if finding_count:
                return "in_use"

        export_tables = get_table_columns(c, "report_exports")
        if export_tables:
            c.execute(
                "SELECT COUNT(*) AS n FROM report_exports WHERE scope_kind = 'application' AND scope_id = ?",
                (app_id,),
            )
            export_row = c.fetchone()
            export_count = int(export_row[0] if not isinstance(export_row, dict) else export_row["n"])
            if export_count:
                return "in_use"

        if "environment_id" in record_columns:
            c.execute(
                """
                UPDATE records
                SET application_id = NULL, environment_id = NULL
                WHERE application_id = ?
                """,
                (app_id,),
            )
            c.execute("DELETE FROM environments WHERE application_id = ?", (app_id,))
        else:
            c.execute("UPDATE records SET application_id = NULL WHERE application_id = ?", (app_id,))
        c.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        conn.commit()
    return "ok"


def assign_hosts(
    application_id: int,
    record_ids: List[int],
    environment_id: int,
    in_scope: Optional[bool] = None,
    db_path: str = DB_PATH,
) -> int:
    if not record_ids:
        return 0
    with get_db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id FROM environments WHERE id = ? AND application_id = ?",
            (environment_id, application_id),
        )
        if not c.fetchone():
            raise ValueError("environment_not_found")
        placeholders = ",".join("?" for _ in record_ids)
        if in_scope is None:
            c.execute(
                f"""
                UPDATE records
                SET environment_id = ?,
                    application_id = ?,
                    env_suggestion = ''
                WHERE id IN ({placeholders})
                """,
                tuple([environment_id, application_id, *record_ids]),
            )
        else:
            c.execute(
                f"""
                UPDATE records
                SET environment_id = ?,
                    application_id = ?,
                    in_scope = ?,
                    env_suggestion = ''
                WHERE id IN ({placeholders})
                """,
                tuple([environment_id, application_id, bool(in_scope), *record_ids]),
            )
        updated = c.rowcount
        conn.commit()
    return updated
