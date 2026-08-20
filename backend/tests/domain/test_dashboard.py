from datetime import datetime, timedelta, timezone

from app.domain.dashboard import WEEK_COUNT, build_findings_summary, severity_key_from_score


def test_severity_key_matches_frontend_bands():
    assert severity_key_from_score(9) == "critical"
    assert severity_key_from_score(7) == "high"
    assert severity_key_from_score(4) == "medium"
    assert severity_key_from_score(0.1) == "low"
    assert severity_key_from_score(0) == "none"
    assert severity_key_from_score(None) == "none"


def test_build_findings_summary_excludes_drafts_and_counts_open_by_severity():
    now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    summary = build_findings_summary(
        [
            {
                "id": "open-crit",
                "title": "SQLi",
                "status": "open",
                "base_score": 9.8,
                "application_id": 1,
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=2),
            },
            {
                "id": "draft",
                "title": "Hidden",
                "status": "draft",
                "base_score": 10,
                "application_id": 1,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "fixed",
                "title": "XSS",
                "status": "fixed",
                "base_score": 7.5,
                "application_id": 2,
                "created_at": now - timedelta(days=10),
                "updated_at": now - timedelta(days=1),
            },
        ],
        now=now,
        week_count=4,
        recent_limit=8,
    )

    assert summary["open"] == 1
    assert summary["closed"] == 1
    assert summary["bySeverity"]["critical"] == 1
    assert summary["bySeverity"]["high"] == 0
    assert len(summary["weekly"]) == 4
    assert summary["recent"][0]["id"] == "open-crit"
    ids = {item["id"] for item in summary["recent"]}
    assert "draft" not in ids


def test_weekly_stock_keeps_open_findings_until_they_close():
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)  # Monday
    created = now - timedelta(days=14)
    closed_at = now - timedelta(days=3)
    summary = build_findings_summary(
        [
            {
                "id": "aging",
                "title": "Aging",
                "status": "fixed",
                "base_score": 8,
                "application_id": 3,
                "created_at": created,
                "updated_at": closed_at,
            }
        ],
        now=now,
        week_count=4,
    )

    assert [week["opened"] for week in summary["weekly"]] == [0, 1, 0, 0]
    assert summary["weekly"][2]["closed"] == 1
    assert summary["weekly"][0]["openStock"] == 0
    assert summary["weekly"][1]["openStock"] == 1
    assert summary["weekly"][2]["openStock"] == 0
    assert summary["weekly"][-1]["openStock"] == 0


def test_empty_rows_still_emit_week_buckets():
    summary = build_findings_summary([], week_count=WEEK_COUNT)
    assert summary["open"] == 0
    assert len(summary["weekly"]) == WEEK_COUNT
    assert summary["weekly"][0]["opened"] == 0
