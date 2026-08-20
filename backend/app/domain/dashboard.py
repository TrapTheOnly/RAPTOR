"""Pure dashboard aggregates. Keep SQL and HTTP out of this module."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

CLOSED_FINDING_STATUSES = {"fixed", "accepted", "not_affected"}
OPEN_FINDING_STATUSES = {"open", "retest"}
WEEK_COUNT = 26
RECENT_FINDING_LIMIT = 8

EMPTY_FINDINGS_SUMMARY: Dict[str, Any] = {
    "open": 0,
    "closed": 0,
    "bySeverity": {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "none": 0,
    },
    "weekly": [],
    "recent": [],
}


def severity_key_from_score(score: Any) -> str:
    try:
        numeric = float(score or 0)
    except (TypeError, ValueError):
        numeric = 0.0
    if numeric >= 9:
        return "critical"
    if numeric >= 7:
        return "high"
    if numeric >= 4:
        return "medium"
    if numeric >= 0.1:
        return "low"
    return "none"


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def monday_of(moment: datetime) -> datetime:
    local = moment.astimezone(timezone.utc)
    start = datetime(local.year, local.month, local.day, tzinfo=timezone.utc)
    weekday = start.weekday()
    return start - timedelta(days=weekday)


def _week_label(start: datetime) -> str:
    return start.strftime("%b ") + str(start.day)


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def build_findings_summary(
    rows: List[Dict[str, Any]],
    now: Optional[datetime] = None,
    week_count: int = WEEK_COUNT,
    recent_limit: int = RECENT_FINDING_LIMIT,
) -> Dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    by_severity = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "none": 0,
    }
    open_count = 0
    closed_count = 0
    usable: List[Dict[str, Any]] = []

    for raw in rows or []:
        status = str(raw.get("status") or "open").strip().lower()
        if status == "draft":
            continue
        created = parse_datetime(raw.get("created_at") or raw.get("createdAt"))
        updated = parse_datetime(raw.get("updated_at") or raw.get("updatedAt"))
        closed = status in CLOSED_FINDING_STATUSES
        closed_at = updated if closed else None
        item = {
            "id": raw.get("id"),
            "title": str(raw.get("title") or "").strip(),
            "status": status or "open",
            "baseScore": float(raw.get("base_score") or raw.get("baseScore") or 0),
            "applicationId": raw.get("application_id") if raw.get("application_id") is not None else raw.get("applicationId"),
            "createdAt": created,
            "closedAt": closed_at,
            "closed": closed,
        }
        usable.append(item)
        if closed:
            closed_count += 1
        elif status in OPEN_FINDING_STATUSES or not closed:
            open_count += 1
            by_severity[severity_key_from_score(item["baseScore"])] += 1

    this_monday = monday_of(moment)
    weeks: List[Dict[str, Any]] = []
    for offset in range(week_count - 1, -1, -1):
        start = this_monday - timedelta(days=offset * 7)
        end = start + timedelta(days=7) - timedelta(microseconds=1)
        opened = 0
        closed_in_week = 0
        open_stock = 0
        for item in usable:
            created = item["createdAt"] or moment
            if start <= created <= end:
                opened += 1
            closed_at = item["closedAt"]
            if closed_at and start <= closed_at <= end:
                closed_in_week += 1
            if created > end:
                continue
            if closed_at and closed_at <= end:
                continue
            open_stock += 1
        weeks.append(
            {
                "label": _week_label(start),
                "weekStart": _iso(start),
                "opened": opened,
                "closed": closed_in_week,
                "openStock": open_stock,
            }
        )

    recent_sorted = sorted(
        usable,
        key=lambda item: (item["createdAt"] or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    recent = [
        {
            "id": item["id"],
            "title": item["title"] or "Untitled finding",
            "status": item["status"],
            "baseScore": item["baseScore"],
            "applicationId": item["applicationId"],
            "createdAt": _iso(item["createdAt"]),
        }
        for item in recent_sorted[:recent_limit]
    ]

    return {
        "open": open_count,
        "closed": closed_count,
        "bySeverity": by_severity,
        "weekly": weeks,
        "recent": recent,
    }


__all__ = [
    "CLOSED_FINDING_STATUSES",
    "EMPTY_FINDINGS_SUMMARY",
    "OPEN_FINDING_STATUSES",
    "RECENT_FINDING_LIMIT",
    "WEEK_COUNT",
    "build_findings_summary",
    "monday_of",
    "parse_datetime",
    "severity_key_from_score",
]
