"""Titles for wave engagements and finding ids on Burp proposals."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def up(cursor):
    _add_column(cursor, "burp_jobs", "title", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "scan_jobs", "title", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "burp_proposals", "finding_id", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "burp_proposals", "accepted_at", "TIMESTAMPTZ")
