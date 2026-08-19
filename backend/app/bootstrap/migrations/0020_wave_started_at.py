"""Waves start explicitly; host lifecycle follows start and end."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def up(cursor):
    _add_column(cursor, "engagement_waves", "started_at", "TIMESTAMPTZ")
    cursor.execute(
        """
        UPDATE engagement_waves
        SET started_at = opened_at
        WHERE started_at IS NULL AND status = 'open' AND opened_at IS NOT NULL
        """
    )
