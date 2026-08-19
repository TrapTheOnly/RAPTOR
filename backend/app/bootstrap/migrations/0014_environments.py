"""Phase 2a application environments and host assignment columns."""

from app.integrations.db.connection import get_table_columns

ENV_TEMPLATES = (
    ("unassigned", "Unassigned", False, False),
    ("prod", "Production", True, True),
    ("stg", "Staging", False, False),
    ("pp", "Preprod", False, False),
    ("qa", "QA", False, False),
)

APP_COLUMNS = (
    ("owner", "TEXT NOT NULL DEFAULT ''"),
    ("data_class", "TEXT NOT NULL DEFAULT ''"),
    ("roe_link", "TEXT NOT NULL DEFAULT ''"),
    ("cookie_domain", "TEXT NOT NULL DEFAULT ''"),
    ("idp", "TEXT NOT NULL DEFAULT ''"),
    ("token_audience", "TEXT NOT NULL DEFAULT ''"),
    ("app_lead", "TEXT NOT NULL DEFAULT ''"),
)


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _seed_environments(cursor) -> None:
    cursor.execute("SELECT id FROM applications")
    app_ids = []
    for row in cursor.fetchall() or []:
        if isinstance(row, dict):
            app_ids.append(int(row["id"]))
        else:
            app_ids.append(int(row[0]))
    for app_id in app_ids:
        for slug, display_name, is_production, include_in_exec_report in ENV_TEMPLATES:
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
                    app_id,
                    slug,
                    display_name,
                    1 if is_production else 0,
                    1 if include_in_exec_report else 0,
                    app_id,
                    slug,
                ),
            )


def _backfill_host_envs(cursor) -> None:
    cursor.execute(
        """
        UPDATE records
        SET environment_id = (
            SELECT e.id
            FROM environments e
            WHERE e.application_id = records.application_id
              AND e.slug = 'unassigned'
            LIMIT 1
        )
        WHERE application_id IS NOT NULL
          AND application_id != 0
          AND environment_id IS NULL
        """
    )
    cursor.execute(
        """
        UPDATE records
        SET in_scope = TRUE
        WHERE id IN (
            SELECT r.id
            FROM records r
            LEFT JOIN pentest_data p ON p.record_id = r.id
            WHERE COALESCE(p.status, 'Not Started') IN ('In Progress', 'Completed')
               OR EXISTS (
                    SELECT 1
                    FROM pentest_findings f
                    WHERE f.record_id = r.id
                      AND COALESCE(f.source, 'human') = 'human'
                      AND COALESCE(f.status, 'open') <> 'draft'
               )
        )
        """
    )


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS environments (
            id SERIAL PRIMARY KEY,
            application_id INTEGER NOT NULL REFERENCES applications(id),
            slug TEXT NOT NULL,
            display_name TEXT NOT NULL,
            is_production INTEGER NOT NULL DEFAULT 0,
            include_in_exec_report INTEGER NOT NULL DEFAULT 0,
            allow_destructive INTEGER NOT NULL DEFAULT 0,
            roe_text TEXT NOT NULL DEFAULT '',
            contacts TEXT NOT NULL DEFAULT '',
            data_class TEXT NOT NULL DEFAULT '',
            in_scope_urls TEXT NOT NULL DEFAULT '',
            out_of_scope_urls TEXT NOT NULL DEFAULT '',
            creds_vault_pointer TEXT NOT NULL DEFAULT '',
            test_window TEXT NOT NULL DEFAULT '',
            UNIQUE (application_id, slug)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_environments_application_id ON environments (application_id)"
    )

    for name, ddl in APP_COLUMNS:
        _add_column(cursor, "applications", name, ddl)

    _add_column(cursor, "records", "environment_id", "INTEGER")
    _add_column(cursor, "records", "in_scope", "BOOLEAN NOT NULL DEFAULT FALSE")
    _add_column(cursor, "records", "env_suggestion", "TEXT NOT NULL DEFAULT ''")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_environment_id ON records (environment_id)"
    )

    _seed_environments(cursor)
    _backfill_host_envs(cursor)
