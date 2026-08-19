"""Track when an occurrence last changed status so weekly charts can freeze."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def up(cursor):
    _add_column(cursor, "finding_occurrences", "status_changed_at", "TIMESTAMPTZ")
    cursor.execute(
        """
        UPDATE finding_occurrences
        SET status_changed_at = COALESCE(updated_at, created_at, NOW())
        WHERE status_changed_at IS NULL
        """
    )
