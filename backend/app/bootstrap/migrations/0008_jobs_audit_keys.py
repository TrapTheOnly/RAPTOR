"""Phase 0 jobs, audit log, scanner destructive flag, hash-only API keys."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_jobs (
            id SERIAL PRIMARY KEY,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            run_after TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            locked_at TIMESTAMPTZ,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_app_jobs_status_run_after ON app_jobs (status, run_after)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id SERIAL PRIMARY KEY,
            at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actor TEXT NOT NULL DEFAULT '',
            actor_type TEXT NOT NULL DEFAULT 'user',
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL DEFAULT '',
            entity_id TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_at ON audit_events (at)")

    columns = get_table_columns(cursor, "scanner_config")
    if "allow_destructive_tools" not in columns:
        cursor.execute(
            "ALTER TABLE scanner_config ADD COLUMN allow_destructive_tools INTEGER NOT NULL DEFAULT 0"
        )

    key_columns = get_table_columns(cursor, "service_account_api_keys")
    if "api_key_hash" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN api_key_hash TEXT")
        cursor.execute(
            """
            UPDATE service_account_api_keys
            SET api_key_hash = api_key_fingerprint
            WHERE api_key_hash IS NULL AND api_key_fingerprint IS NOT NULL
            """
        )
    cursor.execute(
        "ALTER TABLE service_account_api_keys ALTER COLUMN api_key DROP NOT NULL"
    )
    cursor.execute(
        """
        ALTER TABLE service_account_api_keys
        DROP CONSTRAINT IF EXISTS service_account_api_keys_api_key_key
        """
    )
    cursor.execute("UPDATE service_account_api_keys SET api_key = NULL")
