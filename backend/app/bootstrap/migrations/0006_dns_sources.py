"""Phase 0 identity: dns_sources, dns_observations, unique record names."""


def _table_exists(cursor, name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = ?
        """,
        (name,),
    )
    return cursor.fetchone() is not None


def _merge_duplicate_record_names(cursor) -> None:
    cursor.execute(
        """
        CREATE TEMP TABLE _dup_record_map AS
        SELECT r.id AS dup_id, k.keep_id
        FROM records r
        JOIN (
            SELECT name, MIN(id) AS keep_id
            FROM records
            GROUP BY name
            HAVING COUNT(*) > 1
        ) k ON k.name = r.name
        WHERE r.id <> k.keep_id
        """
    )

    cursor.execute(
        """
        DELETE FROM pentest_data d
        USING _dup_record_map m
        WHERE d.record_id = m.dup_id
          AND EXISTS (
              SELECT 1 FROM pentest_data p WHERE p.record_id = m.keep_id
          )
        """
    )
    cursor.execute(
        """
        UPDATE pentest_data d
        SET record_id = m.keep_id
        FROM _dup_record_map m
        WHERE d.record_id = m.dup_id
        """
    )
    cursor.execute(
        """
        DELETE FROM pentest_data a
        USING pentest_data b
        WHERE a.id > b.id AND a.record_id = b.record_id
        """
    )

    cursor.execute(
        """
        DELETE FROM pentest_collaborators c
        USING _dup_record_map m
        WHERE c.record_id = m.dup_id
          AND EXISTS (
              SELECT 1
              FROM pentest_collaborators x
              WHERE x.record_id = m.keep_id AND x.username = c.username
          )
        """
    )
    cursor.execute(
        """
        UPDATE pentest_collaborators c
        SET record_id = m.keep_id
        FROM _dup_record_map m
        WHERE c.record_id = m.dup_id
        """
    )

    cursor.execute(
        """
        UPDATE record_history h
        SET record_id = m.keep_id
        FROM _dup_record_map m
        WHERE h.record_id = m.dup_id
        """
    )

    if _table_exists(cursor, "scan_events"):
        cursor.execute(
            """
            UPDATE scan_events e
            SET record_id = m.keep_id
            FROM _dup_record_map m
            WHERE e.record_id = m.dup_id
            """
        )

    cursor.execute(
        """
        DELETE FROM records r
        USING _dup_record_map m
        WHERE r.id = m.dup_id
        """
    )
    cursor.execute("DROP TABLE _dup_record_map")


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
    _merge_duplicate_record_names(cursor)
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
