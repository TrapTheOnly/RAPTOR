from app.bootstrap.seed_data import (
    create_vuln_categories_table,
    seed_default_vuln_categories,
    seed_report_templates,
    seed_service_checklists,
)
from app.integrations.db.connection import DatabaseCursor


def run_seed_routines(cursor: DatabaseCursor) -> None:
    seed_service_checklists(cursor)
    seed_report_templates(cursor)
    create_vuln_categories_table(cursor)
    seed_default_vuln_categories(cursor)


__all__ = ["run_seed_routines"]
