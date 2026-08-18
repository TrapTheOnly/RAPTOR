"""Collector refresh interval and collect-now request flag."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    columns = get_table_columns(cursor, "collector_agents")
    if "interval_seconds" not in columns:
        cursor.execute(
            "ALTER TABLE collector_agents ADD COLUMN interval_seconds INTEGER NOT NULL DEFAULT 300"
        )
    if "collect_requested_at" not in columns:
        cursor.execute("ALTER TABLE collector_agents ADD COLUMN collect_requested_at TIMESTAMPTZ")
