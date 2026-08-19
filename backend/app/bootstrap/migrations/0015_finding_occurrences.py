"""Phase 2a finding identity: extra columns and occurrence rows."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _backfill_occurrences_and_app(cursor) -> None:
    cursor.execute(
        """
        INSERT INTO finding_occurrences (finding_id, record_id, status)
        SELECT f.id, f.record_id, COALESCE(f.status, 'open')
        FROM pentest_findings f
        WHERE NOT EXISTS (
            SELECT 1
            FROM finding_occurrences o
            WHERE o.finding_id = f.id
              AND o.record_id = f.record_id
        )
        """
    )
    cursor.execute(
        """
        UPDATE pentest_findings
        SET application_id = (
            SELECT r.application_id
            FROM records r
            WHERE r.id = pentest_findings.record_id
        )
        WHERE application_id IS NULL
        """
    )
    cursor.execute(
        """
        UPDATE pentest_findings
        SET title = LEFT(COALESCE(NULLIF(description, ''), category_name, 'Finding'), 200)
        WHERE title IS NULL OR BTRIM(title) = ''
        """
    )


def up(cursor):
    _add_column(cursor, "pentest_findings", "title", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "pentest_findings", "auth_context", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "pentest_findings", "ticket_url", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "pentest_findings", "application_id", "INTEGER")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_pentest_findings_application_id ON pentest_findings (application_id)"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS finding_occurrences (
            finding_id TEXT NOT NULL REFERENCES pentest_findings(id) ON DELETE CASCADE,
            record_id INTEGER NOT NULL REFERENCES records(id),
            status TEXT NOT NULL DEFAULT 'open',
            primary_url TEXT NOT NULL DEFAULT '',
            severity_override TEXT NOT NULL DEFAULT '',
            evidence_note TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (finding_id, record_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_finding_occurrences_record_id ON finding_occurrences (record_id)"
    )
    _backfill_occurrences_and_app(cursor)
