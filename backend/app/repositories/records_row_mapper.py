from typing import Any, Dict, List


def rows_to_dicts(rows: List[Any]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


def determine_source_with_cursor(cursor: Any, ip: str) -> str:
    cursor.execute("SELECT source_name FROM ip_sources WHERE ip_address = ?", (ip,))
    row = cursor.fetchone()
    return row[0] if row else "Other"


RECORD_WITH_PENTEST_AND_APP_SELECT = """
    SELECT
        r.id,
        r.name,
        r.ip_address,
        r.source,
        r.status,
        r.origin,
        r.sync_conflict,
        r.sync_conflict_reason,
        r.creation_date,
        r.last_modification_date,
        r.application_owner,
        r.maintainer,
        r.description,
        r.application_id,
        r.environment_id,
        r.in_scope,
        r.env_suggestion,
        p.open_ports,
        a.name AS application_name,
        e.slug AS environment_slug,
        e.display_name AS environment_name
    FROM records r
    LEFT JOIN pentest_data p ON r.id = p.record_id
    LEFT JOIN applications a ON r.application_id = a.id
    LEFT JOIN environments e ON r.environment_id = e.id
"""


__all__ = [
    "RECORD_WITH_PENTEST_AND_APP_SELECT",
    "determine_source_with_cursor",
    "rows_to_dicts",
]
