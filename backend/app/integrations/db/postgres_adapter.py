import os
import sqlite3
import threading

from app.integrations.db.sqlite_compat import SQLiteCompatConnection, psycopg2

_PATCH_LOCK = threading.Lock()
_PATCHED = False


def _database_url():
    return (os.getenv("DATABASE_URL", "") or "").strip()


def _postgres_connect(_database, *args, **kwargs):
    return SQLiteCompatConnection(_database_url())


def ensure_db_backend():
    """
    Patch sqlite3.connect to route through PostgreSQL compatibility layer.
    PostgreSQL is mandatory; the application no longer supports SQLite runtime mode.
    """
    global _PATCHED

    if not _database_url():
        raise RuntimeError("DATABASE_URL is required. SQLite runtime mode is not supported.")

    if psycopg2 is None:
        raise RuntimeError("PostgreSQL backend requires psycopg2. Install requirements and retry.")

    with _PATCH_LOCK:
        if _PATCHED:
            return True
        if not hasattr(sqlite3, "_original_connect"):
            sqlite3._original_connect = sqlite3.connect
        sqlite3.connect = _postgres_connect  # type: ignore[assignment]
        _PATCHED = True
    return True


__all__ = ["ensure_db_backend"]
