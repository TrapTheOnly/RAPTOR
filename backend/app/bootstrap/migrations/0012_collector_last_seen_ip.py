"""Collector last-seen IP for two-sided ping fallback."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    columns = get_table_columns(cursor, "collector_agents")
    if "last_seen_ip" not in columns:
        cursor.execute("ALTER TABLE collector_agents ADD COLUMN last_seen_ip TEXT NOT NULL DEFAULT ''")
