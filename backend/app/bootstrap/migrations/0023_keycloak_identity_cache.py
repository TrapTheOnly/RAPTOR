"""Identity cache for Keycloak-backed users."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    columns = get_table_columns(cursor, "allowed_users")
    if "keycloak_id" not in columns:
        cursor.execute("ALTER TABLE allowed_users ADD COLUMN keycloak_id TEXT")
    if "password" in columns:
        cursor.execute("ALTER TABLE allowed_users DROP COLUMN IF EXISTS password")
    if "must_reset" in columns:
        cursor.execute("ALTER TABLE allowed_users DROP COLUMN IF EXISTS must_reset")
    key_columns = get_table_columns(cursor, "service_account_api_keys")
    if "keycloak_client_id" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN keycloak_client_id TEXT")
