"""Live wave hosts and per-wave in-scope flags. Membership is no longer a kickoff snapshot."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS engagement_wave_hosts (
            wave_id INTEGER NOT NULL REFERENCES engagement_waves(id) ON DELETE CASCADE,
            record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            in_scope BOOLEAN NOT NULL DEFAULT TRUE,
            PRIMARY KEY (wave_id, record_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_engagement_wave_hosts_record ON engagement_wave_hosts (record_id)"
    )
    columns = get_table_columns(cursor, "engagement_waves")
    if "notes" not in columns:
        cursor.execute("ALTER TABLE engagement_waves ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
