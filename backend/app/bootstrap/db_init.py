import logging

from app.bootstrap.migration_runner import run_migrations
from app.bootstrap.seed_orchestrator import run_seed_routines
from app.config import DB_PATH
from app.integrations.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def init_db(db_path: str = DB_PATH) -> None:
    logger.info("Initializing database...")
    conn = get_db_connection(db_path)
    c = conn.cursor()

    run_migrations(c)
    run_seed_routines(c)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")


__all__ = ["init_db"]
