"""Server-side Keycloak token cache for browser BFF sessions."""


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sso_session_tokens (
            session_key TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            access_expires_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sso_session_tokens_username
        ON sso_session_tokens (username)
        """
    )
