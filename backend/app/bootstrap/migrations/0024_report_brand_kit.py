"""Org-level report brand kit: company name, print ink, logo."""

from app.integrations.db.connection import get_table_columns


def up(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS report_brand_kits (
            id INTEGER PRIMARY KEY,
            company_name TEXT NOT NULL,
            print_ink TEXT NOT NULL,
            logo_asset_id INTEGER,
            updated_by TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS report_kit_logo_assets (
            id SERIAL PRIMARY KEY,
            file_path TEXT NOT NULL UNIQUE,
            created_by TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO report_brand_kits (id, company_name, print_ink, logo_asset_id, updated_by, updated_at)
        SELECT 1, 'Security Operations', '#067A8A', NULL, 'system', (NOW() + INTERVAL '4 hours')
        WHERE NOT EXISTS (SELECT 1 FROM report_brand_kits WHERE id = 1)
        """
    )
    # Backfill company name from the canonical system template when present.
    columns = get_table_columns(cursor, "report_templates")
    if "template_json" in columns:
        cursor.execute(
            """
            SELECT template_json FROM report_templates
            WHERE key = 'manager_executive'
            ORDER BY id ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if row:
            raw = row["template_json"] if isinstance(row, dict) else row[0]
            try:
                import json

                parsed = json.loads(raw) if isinstance(raw, str) else raw
                branding = (parsed or {}).get("branding") or {}
                company = str(branding.get("company_name") or "").strip()
                if company:
                    cursor.execute(
                        "UPDATE report_brand_kits SET company_name = ? WHERE id = 1",
                        (company[:120],),
                    )
            except Exception:
                pass
