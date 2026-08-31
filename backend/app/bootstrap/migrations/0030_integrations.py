"""Jira and DefectDojo connections, ticket templates, field maps, and export history."""


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_connections (
            id SERIAL PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('jira', 'defectdojo')),
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            auth_type TEXT NOT NULL DEFAULT 'api_token',
            auth_email TEXT,
            secret_ciphertext TEXT,
            extra_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'draft',
            last_error TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_templates (
            id SERIAL PRIMARY KEY,
            connection_id INTEGER NOT NULL REFERENCES integration_connections(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            external_project_key TEXT,
            external_project_name TEXT,
            issue_type_id TEXT,
            issue_type_name TEXT,
            extra_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS integration_templates_connection_idx
        ON integration_templates (connection_id)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_field_maps (
            id SERIAL PRIMARY KEY,
            template_id INTEGER NOT NULL REFERENCES integration_templates(id) ON DELETE CASCADE,
            raptor_field TEXT NOT NULL DEFAULT '',
            external_field_id TEXT NOT NULL,
            external_field_name TEXT,
            external_field_type TEXT NOT NULL DEFAULT 'string',
            fill_mode TEXT NOT NULL DEFAULT 'ask',
            static_value TEXT,
            required BOOLEAN NOT NULL DEFAULT FALSE,
            allowed_values_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS integration_field_maps_template_field_idx
        ON integration_field_maps (template_id, external_field_id)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_exports (
            id SERIAL PRIMARY KEY,
            connection_id INTEGER REFERENCES integration_connections(id) ON DELETE SET NULL,
            template_id INTEGER REFERENCES integration_templates(id) ON DELETE SET NULL,
            kind TEXT NOT NULL,
            scope TEXT NOT NULL,
            finding_id TEXT,
            wave_id INTEGER,
            application_id INTEGER,
            external_id TEXT,
            external_url TEXT,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL,
            error TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS integration_exports_finding_idx
        ON integration_exports (finding_id, kind)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS integration_exports_wave_idx
        ON integration_exports (wave_id, kind)
        """
    )
