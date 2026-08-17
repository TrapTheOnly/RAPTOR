"""Phase 0 identity: dns_sources, dns_observations, unique record names."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dns_sources (
            id SERIAL PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            display_name TEXT NOT NULL,
            config TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1,
            last_success_at TIMESTAMPTZ,
            last_error TEXT,
            cursor TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dns_observations (
            id SERIAL PRIMARY KEY,
            source_id INTEGER NOT NULL REFERENCES dns_sources(id),
            fqdn TEXT NOT NULL,
            rrtype TEXT NOT NULL,
            rdata TEXT NOT NULL,
            ttl INTEGER,
            observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            batch_id TEXT
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_dns_observations_source_fqdn ON dns_observations (source_id, fqdn)"
    )
    cursor.execute(
        """
        INSERT INTO dns_sources (key, type, display_name, config, enabled)
        VALUES ('bind_file', 'bind_file', 'BIND zone files', '{}', 1)
        ON CONFLICT (key) DO NOTHING
        """
    )
    cursor.execute(
        """
        DELETE FROM records a
        USING records b
        WHERE a.id > b.id AND a.name = b.name
        """
    )
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_records_name_unique ON records (name)")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_pentest_data_record_id ON pentest_data (record_id)"
    )
    cursor.execute(
        """
        INSERT INTO dns_observations (source_id, fqdn, rrtype, rdata, observed_at, batch_id)
        SELECT s.id, r.name, 'A', r.ip_address, NOW(), 'backfill'
        FROM records r
        CROSS JOIN dns_sources s
        WHERE s.key = 'bind_file'
          AND r.origin = 'automated'
        """
    )
