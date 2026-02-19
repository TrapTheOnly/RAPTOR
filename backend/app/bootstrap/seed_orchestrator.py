import sqlite3

from app.bootstrap.seed_data import (
    create_vuln_categories_table,
    seed_default_vuln_categories,
    seed_report_templates,
    seed_service_checklists,
)


def run_seed_routines(cursor: sqlite3.Cursor) -> None:
    seed_service_checklists(cursor)
    seed_report_templates(cursor)
    create_vuln_categories_table(cursor)
    seed_default_vuln_categories(cursor)


__all__ = ["run_seed_routines"]
