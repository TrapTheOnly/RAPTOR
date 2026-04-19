import importlib
import logging
import pkgutil
from typing import List, Set, Tuple

from app.integrations.db.connection import DatabaseCursor

logger = logging.getLogger(__name__)

BASELINE_VERSION = "0001_baseline"
MIGRATIONS_PACKAGE = "app.bootstrap.migrations"


def ensure_migration_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def get_applied_versions(cursor: DatabaseCursor) -> Set[str]:
    cursor.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def discover_migrations() -> List[Tuple[str, object]]:
    package = importlib.import_module(MIGRATIONS_PACKAGE)
    migrations = []
    for finder, name, is_pkg in pkgutil.iter_modules(package.__path__):
        if is_pkg or name.startswith("_"):
            continue
        module = importlib.import_module(f"{MIGRATIONS_PACKAGE}.{name}")
        if not hasattr(module, "up"):
            logger.warning(f"Migration {name} has no up() function, skipping.")
            continue
        migrations.append((name, module))
    migrations.sort(key=lambda m: m[0])
    return migrations


def _existing_db_needs_baseline(cursor: DatabaseCursor) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'records'
        """,
    )
    return cursor.fetchone() is not None


def run_migrations(cursor: DatabaseCursor) -> None:
    ensure_migration_table(cursor)
    applied = get_applied_versions(cursor)

    if BASELINE_VERSION not in applied and _existing_db_needs_baseline(cursor):
        logger.info(
            f"Existing database detected. Marking {BASELINE_VERSION} as applied."
        )
        cursor.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, (NOW() + INTERVAL '4 hours'))",
            (BASELINE_VERSION,),
        )
        applied.add(BASELINE_VERSION)

    migrations = discover_migrations()
    pending = [(name, mod) for name, mod in migrations if name not in applied]

    if not pending:
        logger.info("No pending migrations.")
        return

    for name, module in pending:
        logger.info(f"Applying migration {name}...")
        module.up(cursor)
        cursor.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, (NOW() + INTERVAL '4 hours'))",
            (name,),
        )
        logger.info(f"Migration {name} applied.")


__all__ = ["run_migrations"]
