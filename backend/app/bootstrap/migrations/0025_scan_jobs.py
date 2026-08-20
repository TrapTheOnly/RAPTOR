"""Wave-scoped AI scan jobs and job_id on scan_events."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_jobs (
            id SERIAL PRIMARY KEY,
            application_id INTEGER NOT NULL,
            wave_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            record_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            launched_by TEXT,
            launched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            provider_type TEXT NOT NULL DEFAULT '',
            model_id TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_jobs_wave ON scan_jobs(wave_id, launched_at DESC)"
    )
    _add_column(cursor, "scan_events", "job_id", "INTEGER")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_events_job_id ON scan_events(job_id, id)"
    )
