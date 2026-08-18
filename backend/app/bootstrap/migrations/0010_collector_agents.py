"""Phase 1 collector agents: enroll tokens, per-server bind_agent sources."""


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS collector_enroll_tokens (
            id SERIAL PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS collector_agents (
            id SERIAL PRIMARY KEY,
            source_id INTEGER NOT NULL REFERENCES dns_sources(id),
            hostname TEXT NOT NULL,
            agent_version TEXT NOT NULL DEFAULT '',
            token_hash TEXT NOT NULL UNIQUE,
            token_rotated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ,
            last_soa_serial TEXT,
            last_zones TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'active',
            enrolled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            enroll_token_id INTEGER REFERENCES collector_enroll_tokens(id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_collector_agents_status ON collector_agents (status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_collector_agents_source_id ON collector_agents (source_id)"
    )
