"""Phase 3 cloud DNS: provider ids and zone on observations."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def up(cursor):
    _add_column(cursor, "dns_observations", "provider_zone_id", "TEXT")
    _add_column(cursor, "dns_observations", "provider_record_id", "TEXT")
    _add_column(cursor, "dns_observations", "zone", "TEXT")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_dns_observations_source_batch ON dns_observations (source_id, batch_id)"
    )
