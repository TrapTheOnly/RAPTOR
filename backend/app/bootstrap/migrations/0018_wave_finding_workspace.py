"""One environment per wave, wave members, finding workspace identity."""

import json

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _backfill_wave_environment(cursor) -> None:
    columns = get_table_columns(cursor, "engagement_waves")
    if "environment_id" not in columns:
        return
    cursor.execute("SELECT id, env_ids, environment_id FROM engagement_waves")
    for row in cursor.fetchall() or []:
        if isinstance(row, dict):
            wave_id = row.get("id")
            env_ids_raw = row.get("env_ids")
            current = row.get("environment_id")
        else:
            wave_id, env_ids_raw, current = row[0], row[1], row[2]
        if current not in (None, ""):
            continue
        try:
            parsed = json.loads(env_ids_raw or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = []
        if not parsed:
            continue
        try:
            env_id = int(parsed[0])
        except (TypeError, ValueError, IndexError):
            continue
        cursor.execute(
            "UPDATE engagement_waves SET environment_id = ? WHERE id = ?",
            (env_id, wave_id),
        )
        cursor.execute(
            "UPDATE engagement_waves SET env_ids = ? WHERE id = ?",
            (json.dumps([env_id]), wave_id),
        )


def up(cursor):
    _add_column(cursor, "engagement_waves", "environment_id", "INTEGER")
    _add_column(cursor, "pentest_findings", "discovered_wave_id", "INTEGER")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS engagement_wave_members (
            wave_id INTEGER NOT NULL REFERENCES engagement_waves(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            PRIMARY KEY (wave_id, username)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS finding_collaborators (
            finding_id TEXT NOT NULL REFERENCES pentest_findings(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            PRIMARY KEY (finding_id, username)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_engagement_waves_environment_id ON engagement_waves (environment_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_pentest_findings_discovered_wave_id ON pentest_findings (discovered_wave_id)"
    )
    _backfill_wave_environment(cursor)
