"""Add scan_events table for live AI progress tracking."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_events (
            id BIGSERIAL PRIMARY KEY,
            record_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scan_events_record_id ON scan_events(record_id, id)"
    )
