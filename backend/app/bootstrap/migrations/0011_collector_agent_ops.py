"""Collector agent identity, contact mode, and ingest timestamps."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    columns = get_table_columns(cursor, "collector_agents")
    if "display_name" not in columns:
        cursor.execute(
            "ALTER TABLE collector_agents ADD COLUMN display_name TEXT NOT NULL DEFAULT ''"
        )
        cursor.execute(
            "UPDATE collector_agents SET display_name = hostname WHERE display_name = ''"
        )
    if "mode" not in columns:
        cursor.execute(
            "ALTER TABLE collector_agents ADD COLUMN mode TEXT NOT NULL DEFAULT 'one_sided'"
        )
    if "callback_url" not in columns:
        cursor.execute(
            "ALTER TABLE collector_agents ADD COLUMN callback_url TEXT NOT NULL DEFAULT ''"
        )
    if "last_ingest_at" not in columns:
        cursor.execute("ALTER TABLE collector_agents ADD COLUMN last_ingest_at TIMESTAMPTZ")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_collector_agents_last_seen ON collector_agents (last_seen_at DESC)"
    )
