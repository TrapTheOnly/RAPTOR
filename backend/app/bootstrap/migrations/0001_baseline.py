"""Baseline migration — establishes all tables that existed before the migration system."""

from app.bootstrap.schema_setup import (
    create_allowed_users_table,
    create_app_meta_table,
    create_applications_table,
    create_auth_lockout_table,
    create_ip_sources_table,
    create_pentest_collaborators_table,
    create_pentest_table,
    create_record_history_table,
    create_records_table,
    create_report_templates_table,
    create_service_account_api_keys_table,
    create_service_checklists_table,
    repair_legacy_application_mapping,
)


def up(cursor):
    record_columns = create_records_table(cursor)
    create_allowed_users_table(cursor)
    create_applications_table(cursor)
    repair_legacy_application_mapping(cursor, record_columns)
    create_ip_sources_table(cursor)
    create_record_history_table(cursor)
    create_pentest_table(cursor)
    create_pentest_collaborators_table(cursor)
    create_service_checklists_table(cursor)
    create_report_templates_table(cursor)
    create_service_account_api_keys_table(cursor)
    create_app_meta_table(cursor)
    create_auth_lockout_table(cursor)
