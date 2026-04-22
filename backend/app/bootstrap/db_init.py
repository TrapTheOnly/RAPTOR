import logging

from app.bootstrap.schema_setup import (
    create_allowed_users_table,
    create_app_meta_table,
    create_applications_table,
    create_auth_lockout_table,
    create_email_config_table,
    create_ip_sources_table,
    create_notifications_table,
    create_pentest_collaborators_table,
    create_pentest_table,
    create_record_history_table,
    create_records_table,
    create_report_templates_table,
    create_scanner_config_table,
    create_service_account_api_keys_table,
    create_service_checklists_table,
    repair_legacy_application_mapping,
)
from app.bootstrap.migration_runner import run_migrations
from app.bootstrap.seed_orchestrator import run_seed_routines
from app.config import DB_PATH
from app.integrations.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def init_db(db_path: str = DB_PATH) -> None:
    logger.info("Initializing database...")
    conn = get_db_connection(db_path)
    c = conn.cursor()

    record_columns = create_records_table(c)
    create_allowed_users_table(c)
    create_applications_table(c)
    repair_legacy_application_mapping(c, record_columns)
    create_ip_sources_table(c)
    create_record_history_table(c)
    create_pentest_table(c)
    create_pentest_collaborators_table(c)
    create_service_checklists_table(c)
    create_report_templates_table(c)
    create_service_account_api_keys_table(c)
    create_app_meta_table(c)
    create_auth_lockout_table(c)
    create_notifications_table(c)
    create_email_config_table(c)
    create_scanner_config_table(c)
    run_seed_routines(c)
    run_migrations(c)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")


__all__ = ["init_db"]
