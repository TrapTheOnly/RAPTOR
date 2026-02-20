from typing import Set

from app.integrations.db.connection import DatabaseCursor, get_table_columns


def create_records_table(cursor: DatabaseCursor) -> Set[str]:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unchanged',
            creation_date TEXT NOT NULL,
            last_modification_date TEXT,
            application_owner TEXT DEFAULT '',
            maintainer TEXT DEFAULT '',
            description TEXT DEFAULT '',
            application_id INTEGER
        )
        """
    )
    record_columns = get_table_columns(cursor, "records")
    if "application_id" not in record_columns:
        cursor.execute("ALTER TABLE records ADD COLUMN application_id INTEGER")
        record_columns.add("application_id")
    return record_columns


def create_allowed_users_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS allowed_users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            added_date TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            auth_type TEXT NOT NULL DEFAULT 'ldap',
            password BYTEA,
            must_reset INTEGER NOT NULL DEFAULT 0,
            permissions TEXT
        )
        """
    )
    allowed_user_columns = get_table_columns(cursor, "allowed_users")
    if "auth_type" not in allowed_user_columns:
        cursor.execute("ALTER TABLE allowed_users ADD COLUMN auth_type TEXT NOT NULL DEFAULT 'ldap'")
    if "password" not in allowed_user_columns:
        cursor.execute("ALTER TABLE allowed_users ADD COLUMN password BYTEA")
    if "must_reset" not in allowed_user_columns:
        cursor.execute("ALTER TABLE allowed_users ADD COLUMN must_reset INTEGER NOT NULL DEFAULT 0")
    if "permissions" not in allowed_user_columns:
        cursor.execute("ALTER TABLE allowed_users ADD COLUMN permissions TEXT")
    cursor.execute("UPDATE allowed_users SET auth_type = 'ldap' WHERE auth_type IS NULL OR auth_type = ''")


def create_applications_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_by TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def repair_legacy_application_mapping(cursor: DatabaseCursor, record_columns: Set[str]) -> None:
    if "application_name" not in record_columns:
        return

    cursor.execute(
        """
        UPDATE records
        SET application_id = (
            SELECT a.id
            FROM applications a
            WHERE a.name = records.application_name
            LIMIT 1
        )
        WHERE (application_id IS NULL OR application_id = 0)
          AND application_name IS NOT NULL
          AND TRIM(application_name) != ''
          AND EXISTS (
              SELECT 1
              FROM applications a
              WHERE a.name = records.application_name
          )
        """
    )
    cursor.execute(
        """
        UPDATE records
        SET application_name = (
            SELECT a.name
            FROM applications a
            WHERE a.id = records.application_id
            LIMIT 1
        )
        WHERE application_id IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM applications a
              WHERE a.id = records.application_id
          )
        """
    )


def create_ip_sources_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ip_sources (
            id SERIAL PRIMARY KEY,
            source_name TEXT NOT NULL,
            ip_address TEXT NOT NULL UNIQUE
        )
        """
    )


def create_record_history_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS record_history (
            id SERIAL PRIMARY KEY,
            record_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL,
            old_ip_address TEXT,
            new_ip_address TEXT,
            old_source TEXT,
            new_source TEXT,
            old_maintainer TEXT,
            new_maintainer TEXT
        )
        """
    )


def create_pentest_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pentest_data (
            id SERIAL PRIMARY KEY,
            record_id INTEGER NOT NULL,
            dns_name TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            source TEXT NOT NULL,
            report_file TEXT,
            vulnerable INTEGER,
            tested_by TEXT,
            test_start_date TEXT,
            test_end_date TEXT,
            vulnerability_fixed INTEGER,
            service_desk_link TEXT,
            status TEXT NOT NULL DEFAULT 'Not Started',
            open_ports TEXT,
            notes TEXT,
            owasp_checklist TEXT,
            checklist_states TEXT,
            vulnerabilities TEXT,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
        """
    )
    pentest_columns = get_table_columns(cursor, "pentest_data")
    if "vulnerabilities" not in pentest_columns:
        cursor.execute("ALTER TABLE pentest_data ADD COLUMN vulnerabilities TEXT")
    if "checklist_states" not in pentest_columns:
        cursor.execute("ALTER TABLE pentest_data ADD COLUMN checklist_states TEXT")
    if "generated_report_file" not in pentest_columns:
        cursor.execute("ALTER TABLE pentest_data ADD COLUMN generated_report_file TEXT")
    if "generated_report_template_id" not in pentest_columns:
        cursor.execute("ALTER TABLE pentest_data ADD COLUMN generated_report_template_id INTEGER")
    if "generated_report_generated_at" not in pentest_columns:
        cursor.execute("ALTER TABLE pentest_data ADD COLUMN generated_report_generated_at TEXT")


def create_service_checklists_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS service_checklists (
            id SERIAL PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            service TEXT NOT NULL,
            source TEXT,
            auto_ports TEXT NOT NULL DEFAULT '[]',
            sections TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            is_system INTEGER NOT NULL DEFAULT 1,
            is_customized INTEGER NOT NULL DEFAULT 0,
            system_revision TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    checklist_columns = get_table_columns(cursor, "service_checklists")
    if "is_system" not in checklist_columns:
        cursor.execute("ALTER TABLE service_checklists ADD COLUMN is_system INTEGER NOT NULL DEFAULT 1")
    if "is_customized" not in checklist_columns:
        cursor.execute("ALTER TABLE service_checklists ADD COLUMN is_customized INTEGER NOT NULL DEFAULT 0")
    if "system_revision" not in checklist_columns:
        cursor.execute("ALTER TABLE service_checklists ADD COLUMN system_revision TEXT")


def create_report_templates_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS report_templates (
            id SERIAL PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            template_json TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            is_system INTEGER NOT NULL DEFAULT 1,
            is_customized INTEGER NOT NULL DEFAULT 0,
            system_revision TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    report_template_columns = get_table_columns(cursor, "report_templates")
    if "description" not in report_template_columns:
        cursor.execute("ALTER TABLE report_templates ADD COLUMN description TEXT")
    if "is_system" not in report_template_columns:
        cursor.execute("ALTER TABLE report_templates ADD COLUMN is_system INTEGER NOT NULL DEFAULT 1")
    if "is_customized" not in report_template_columns:
        cursor.execute("ALTER TABLE report_templates ADD COLUMN is_customized INTEGER NOT NULL DEFAULT 0")
    if "system_revision" not in report_template_columns:
        cursor.execute("ALTER TABLE report_templates ADD COLUMN system_revision TEXT")


def create_app_meta_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def create_auth_lockout_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_lockouts (
            username TEXT PRIMARY KEY,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            lockout_level INTEGER NOT NULL DEFAULT 0,
            lockout_until_epoch INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )


__all__ = [
    "create_allowed_users_table",
    "create_app_meta_table",
    "create_applications_table",
    "create_auth_lockout_table",
    "create_ip_sources_table",
    "create_pentest_table",
    "create_record_history_table",
    "create_records_table",
    "create_report_templates_table",
    "create_service_checklists_table",
    "repair_legacy_application_mapping",
]
