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
            origin TEXT NOT NULL DEFAULT 'automated',
            sync_conflict INTEGER NOT NULL DEFAULT 0,
            sync_conflict_reason TEXT,
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
    if "origin" not in record_columns:
        cursor.execute("ALTER TABLE records ADD COLUMN origin TEXT NOT NULL DEFAULT 'automated'")
        record_columns.add("origin")
    if "sync_conflict" not in record_columns:
        cursor.execute("ALTER TABLE records ADD COLUMN sync_conflict INTEGER NOT NULL DEFAULT 0")
        record_columns.add("sync_conflict")
    if "sync_conflict_reason" not in record_columns:
        cursor.execute("ALTER TABLE records ADD COLUMN sync_conflict_reason TEXT")
        record_columns.add("sync_conflict_reason")
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
            permissions TEXT,
            is_service_account INTEGER NOT NULL DEFAULT 0,
            full_name TEXT
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
    if "is_service_account" not in allowed_user_columns:
        cursor.execute("ALTER TABLE allowed_users ADD COLUMN is_service_account INTEGER NOT NULL DEFAULT 0")
    if "full_name" not in allowed_user_columns:
        cursor.execute("ALTER TABLE allowed_users ADD COLUMN full_name TEXT")
    cursor.execute(
        """
        UPDATE allowed_users
        SET is_service_account = 1
        WHERE auth_type = 'service'
        """
    )
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


def create_pentest_collaborators_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pentest_collaborators (
            id SERIAL PRIMARY KEY,
            record_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            added_by TEXT NOT NULL,
            added_at TEXT NOT NULL,
            UNIQUE(record_id, username),
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
        """
    )


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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS report_template_logo_assets (
            id SERIAL PRIMARY KEY,
            report_template_id INTEGER NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            created_by TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    logo_asset_columns = get_table_columns(cursor, "report_template_logo_assets")
    if "report_template_id" not in logo_asset_columns:
        cursor.execute("ALTER TABLE report_template_logo_assets ADD COLUMN report_template_id INTEGER")
    if "file_path" not in logo_asset_columns:
        cursor.execute("ALTER TABLE report_template_logo_assets ADD COLUMN file_path TEXT")
    if "created_by" not in logo_asset_columns:
        cursor.execute("ALTER TABLE report_template_logo_assets ADD COLUMN created_by TEXT")
    if "created_at" not in logo_asset_columns:
        cursor.execute("ALTER TABLE report_template_logo_assets ADD COLUMN created_at TEXT")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_report_template_logo_assets_template_id
        ON report_template_logo_assets (report_template_id)
        """
    )


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


def create_service_account_api_keys_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS service_account_api_keys (
            id SERIAL PRIMARY KEY,
            service_account_id INTEGER NOT NULL UNIQUE,
            api_key TEXT NOT NULL UNIQUE,
            api_key_fingerprint TEXT NOT NULL UNIQUE,
            scopes TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            rotated_at TEXT,
            last_used_at TEXT,
            created_by TEXT,
            rotated_by TEXT
        )
        """
    )
    key_columns = get_table_columns(cursor, "service_account_api_keys")
    if "service_account_id" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN service_account_id INTEGER")
    if "api_key" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN api_key TEXT")
    if "api_key_fingerprint" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN api_key_fingerprint TEXT")
    if "scopes" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN scopes TEXT NOT NULL DEFAULT '[]'")
    if "created_at" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN created_at TEXT")
    if "expires_at" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN expires_at TEXT")
    if "rotated_at" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN rotated_at TEXT")
    if "last_used_at" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN last_used_at TEXT")
    if "created_by" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN created_by TEXT")
    if "rotated_by" not in key_columns:
        cursor.execute("ALTER TABLE service_account_api_keys ADD COLUMN rotated_by TEXT")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_service_account_api_keys_fingerprint
        ON service_account_api_keys (api_key_fingerprint)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_service_account_api_keys_service_account
        ON service_account_api_keys (service_account_id)
        """
    )


def create_notifications_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            recipient TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            actor TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_notifications_recipient
        ON notifications (recipient)
        """
    )


def create_email_config_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS email_config (
            id SERIAL PRIMARY KEY,
            smtp_host TEXT NOT NULL,
            smtp_port INTEGER NOT NULL DEFAULT 587,
            smtp_user TEXT,
            smtp_password TEXT,
            smtp_use_tls INTEGER NOT NULL DEFAULT 1,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL DEFAULT 'RAPTOR',
            enabled INTEGER NOT NULL DEFAULT 0,
            updated_by TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )


def create_scanner_config_table(cursor: DatabaseCursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scanner_config (
            id SERIAL PRIMARY KEY,
            aws_region TEXT NOT NULL DEFAULT 'us-east-1',
            bedrock_model_id TEXT NOT NULL DEFAULT '',
            cost_limit_usd NUMERIC(10,4) NOT NULL DEFAULT 5.0,
            input_cost_per_1m NUMERIC(10,6) NOT NULL DEFAULT 3.0,
            output_cost_per_1m NUMERIC(10,6) NOT NULL DEFAULT 15.0,
            max_concurrent_scans INTEGER NOT NULL DEFAULT 2,
            enabled INTEGER NOT NULL DEFAULT 0,
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )


__all__ = [
    "create_allowed_users_table",
    "create_app_meta_table",
    "create_applications_table",
    "create_auth_lockout_table",
    "create_email_config_table",
    "create_ip_sources_table",
    "create_notifications_table",
    "create_pentest_collaborators_table",
    "create_pentest_table",
    "create_record_history_table",
    "create_records_table",
    "create_report_templates_table",
    "create_service_account_api_keys_table",
    "create_scanner_config_table",
    "create_service_checklists_table",
    "repair_legacy_application_mapping",
]
