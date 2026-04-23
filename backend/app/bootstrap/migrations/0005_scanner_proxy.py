"""Add proxy_url, proxy_username, proxy_password to scanner_config."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    columns = get_table_columns(cursor, "scanner_config")
    if "proxy_url" not in columns:
        cursor.execute("ALTER TABLE scanner_config ADD COLUMN proxy_url TEXT NOT NULL DEFAULT ''")
    if "proxy_username" not in columns:
        cursor.execute("ALTER TABLE scanner_config ADD COLUMN proxy_username TEXT NOT NULL DEFAULT ''")
    if "proxy_password" not in columns:
        cursor.execute("ALTER TABLE scanner_config ADD COLUMN proxy_password TEXT NOT NULL DEFAULT ''")
