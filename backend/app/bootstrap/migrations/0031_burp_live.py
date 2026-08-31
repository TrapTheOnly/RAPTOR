"""Burp Live: wave-scoped agents, deduped events, auth templates, JWT jobs."""


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS burp_enroll_tokens (
            id SERIAL PRIMARY KEY,
            wave_id INTEGER NOT NULL,
            application_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_burp_enroll_tokens_wave ON burp_enroll_tokens (wave_id)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS burp_agents (
            id SERIAL PRIMARY KEY,
            wave_id INTEGER NOT NULL,
            application_id INTEGER NOT NULL,
            enroll_token_id INTEGER REFERENCES burp_enroll_tokens(id),
            username TEXT NOT NULL DEFAULT '',
            hostname TEXT NOT NULL DEFAULT '',
            burp_version TEXT NOT NULL DEFAULT '',
            token_hash TEXT NOT NULL UNIQUE,
            token_rotated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status TEXT NOT NULL DEFAULT 'active',
            last_seen_ip TEXT NOT NULL DEFAULT '',
            last_heartbeat_at TIMESTAMPTZ,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            enrolled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_burp_agents_wave ON burp_agents (wave_id, status)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS burp_events (
            id SERIAL PRIMARY KEY,
            wave_id INTEGER NOT NULL,
            application_id INTEGER NOT NULL,
            agent_id INTEGER REFERENCES burp_agents(id),
            tool TEXT NOT NULL CHECK (tool IN ('repeater', 'intruder', 'scanner')),
            dedupe_key TEXT NOT NULL,
            host TEXT NOT NULL DEFAULT '',
            path TEXT NOT NULL DEFAULT '',
            method TEXT NOT NULL DEFAULT '',
            status INTEGER,
            count INTEGER NOT NULL DEFAULT 1,
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            excerpt_json TEXT NOT NULL DEFAULT '{}',
            scanner_type TEXT NOT NULL DEFAULT '',
            scanner_name TEXT NOT NULL DEFAULT '',
            scanner_severity TEXT NOT NULL DEFAULT '',
            scanner_confidence TEXT NOT NULL DEFAULT '',
            scanner_parameter TEXT NOT NULL DEFAULT '',
            scanner_detail TEXT NOT NULL DEFAULT '',
            UNIQUE (wave_id, dedupe_key)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_burp_events_wave_path ON burp_events (wave_id, path)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_burp_events_wave_issue ON burp_events (wave_id, scanner_name)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS burp_auth_templates (
            id SERIAL PRIMARY KEY,
            wave_id INTEGER NOT NULL,
            application_id INTEGER NOT NULL,
            agent_id INTEGER REFERENCES burp_agents(id),
            host TEXT NOT NULL DEFAULT '',
            method TEXT NOT NULL DEFAULT 'POST',
            path TEXT NOT NULL DEFAULT '',
            request_ciphertext TEXT NOT NULL DEFAULT '',
            placeholder_map TEXT NOT NULL DEFAULT '{}',
            extract_rule TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (wave_id, host)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS burp_jobs (
            id SERIAL PRIMARY KEY,
            wave_id INTEGER NOT NULL,
            application_id INTEGER NOT NULL,
            agent_id INTEGER REFERENCES burp_agents(id),
            kind TEXT NOT NULL CHECK (kind IN ('jwt', 'analyze')),
            status TEXT NOT NULL DEFAULT 'pending',
            host TEXT NOT NULL DEFAULT '',
            path TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            result_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_burp_jobs_wave ON burp_jobs (wave_id, kind, status)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS burp_proposals (
            id SERIAL PRIMARY KEY,
            wave_id INTEGER NOT NULL,
            application_id INTEGER NOT NULL,
            job_id INTEGER REFERENCES burp_jobs(id),
            kind TEXT NOT NULL DEFAULT 'jwt',
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            result_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_burp_proposals_wave ON burp_proposals (wave_id, status)"
    )
