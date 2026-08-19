"""Phase 2a immutable report export snapshots."""


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS report_exports (
            id SERIAL PRIMARY KEY,
            scope_kind TEXT NOT NULL,
            scope_id INTEGER NOT NULL,
            template_id INTEGER,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            generated_by TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL DEFAULT '',
            source_finding_ids TEXT NOT NULL DEFAULT '[]',
            excluded_draft_count INTEGER NOT NULL DEFAULT 0,
            selected_env_ids TEXT NOT NULL DEFAULT '[]',
            content_hash TEXT NOT NULL DEFAULT '',
            package TEXT NOT NULL DEFAULT 'owner_delivery'
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_exports_scope ON report_exports (scope_kind, scope_id)"
    )
    cursor.execute(
        """
        INSERT INTO report_exports (
            scope_kind, scope_id, template_id, generated_at, generated_by, file_path, package
        )
        SELECT
            'host',
            p.record_id,
            p.generated_report_template_id,
            NOW(),
            COALESCE(p.tested_by, ''),
            p.generated_report_file,
            'host'
        FROM pentest_data p
        WHERE p.generated_report_file IS NOT NULL
          AND BTRIM(p.generated_report_file) <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM report_exports e
              WHERE e.scope_kind = 'host'
                AND e.scope_id = p.record_id
                AND e.file_path = p.generated_report_file
          )
        """
    )
