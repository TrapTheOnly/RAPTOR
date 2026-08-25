"""Finding-level impact, evidence, and remediation fields for report write-ups."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def up(cursor):
    _add_column(cursor, "pentest_findings", "impact", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "pentest_findings", "evidence", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "pentest_findings", "remediation", "TEXT NOT NULL DEFAULT ''")
