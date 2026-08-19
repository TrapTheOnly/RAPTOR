"""Phase 2b waves, env ACL, checklists, zone catalog, shared hosts, signed exports."""

from app.integrations.db.connection import get_table_columns


def _add_column(cursor, table: str, name: str, ddl: str) -> None:
    columns = get_table_columns(cursor, table)
    if name not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def up(cursor):
    _add_column(cursor, "environments", "max_concurrent_scans", "INTEGER NOT NULL DEFAULT 1")
    _add_column(cursor, "report_exports", "signature", "TEXT NOT NULL DEFAULT ''")
    _add_column(cursor, "report_exports", "wave_id", "INTEGER")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS engagement_waves (
            id SERIAL PRIMARY KEY,
            application_id INTEGER NOT NULL REFERENCES applications(id),
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            env_ids TEXT NOT NULL DEFAULT '[]',
            host_snapshot TEXT NOT NULL DEFAULT '[]',
            opened_by TEXT NOT NULL DEFAULT '',
            opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            closed_at TIMESTAMPTZ,
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_engagement_waves_application_id ON engagement_waves (application_id)"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS environment_acl (
            environment_id INTEGER NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            PRIMARY KEY (environment_id, username)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS environment_checklists (
            environment_id INTEGER NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
            template_key TEXT NOT NULL,
            PRIMARY KEY (environment_id, template_key)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dns_zones (
            id SERIAL PRIMARY KEY,
            suffix TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL DEFAULT '',
            application_id INTEGER REFERENCES applications(id),
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shared_host_apps (
            record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            consumer_application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            PRIMARY KEY (record_id, consumer_application_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_shared_host_apps_consumer ON shared_host_apps (consumer_application_id)"
    )
