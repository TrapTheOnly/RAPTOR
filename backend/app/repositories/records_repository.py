"""Compatibility import surface for records repository operations."""

from app.repositories.records_mutation_repository import (
    create_manual_record,
    delete_record,
    resolve_manual_sync_conflict,
    store_records_in_db,
    update_record,
)
from app.repositories.records_query_repository import (
    determine_source,
    fetch_dashboard_data,
    fetch_record_by_domain,
    fetch_record_by_id,
    fetch_record_history,
    fetch_records,
)

__all__ = [
    "create_manual_record",
    "delete_record",
    "determine_source",
    "fetch_dashboard_data",
    "fetch_record_by_domain",
    "fetch_record_by_id",
    "fetch_record_history",
    "fetch_records",
    "resolve_manual_sync_conflict",
    "store_records_in_db",
    "update_record",
]
