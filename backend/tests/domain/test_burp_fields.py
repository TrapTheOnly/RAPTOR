from app.domain.burp.fields import (
    cluster_events,
    enrich_clusters,
    event_fingerprint,
    interesting_intruder,
    jwt_like,
    redact_headers,
    strip_jwts,
)


def test_redact_secret_headers():
    redacted = redact_headers(
        {"Cookie": "a=b", "Set-Cookie": "sid=abc", "Accept": "*/*", "X-Api-Key": "nopenope"}
    )
    assert redacted["Cookie"] == "[REDACTED]"
    assert redacted["Set-Cookie"] == "[REDACTED]"
    assert redacted["X-Api-Key"] == "[REDACTED]"
    assert redacted["Accept"] == "*/*"


def test_strip_jwts_replaces_compact_tokens():
    token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhIn0.signature"
    assert strip_jwts(f"Bearer {token}") == "Bearer [jwt]"


def test_jwt_like_extracts_compact_token():
    token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhIn0.signature"
    assert jwt_like(f"Bearer {token}") == token
    assert jwt_like("not-a-jwt") is None


def test_interesting_intruder_flags_errors():
    assert interesting_intruder(500, 12, "", 12) is True
    assert interesting_intruder(200, 12, "SQL syntax error", 12) is True
    assert interesting_intruder(200, 200, "ok", 12) is True
    assert interesting_intruder(200, 12, "ok", 12) is False


def test_cluster_events_keeps_repeater_and_intruder_apart():
    rows = [
        {"id": 1, "tool": "repeater", "method": "POST", "host": "app.example", "path": "/login", "status": 401, "count": 12},
        {"id": 2, "tool": "intruder", "method": "POST", "host": "app.example", "path": "/login", "status": 500, "count": 2},
        {"id": 3, "tool": "repeater", "method": "GET", "host": "app.example", "path": "/me", "status": 200, "count": 1},
    ]
    clusters = cluster_events(rows)
    assert [(item["tool"], item["path"], item["count"]) for item in clusters] == [
        ("repeater", "/login", 12),
        ("intruder", "/login", 2),
        ("repeater", "/me", 1),
    ]
    assert clusters[0]["statuses"] == {"401": 12}
    assert clusters[1]["statuses"] == {"500": 2}
    assert "5xx" in clusters[1]["flags"]
    first = event_fingerprint(rows)
    assert first == event_fingerprint(rows)
    assert first != event_fingerprint(rows[:2] + [{**rows[2], "count": 9}])


def test_enrich_clusters_status_flip_and_best_exchange():
    rows = [
        {
            "id": 1,
            "tool": "repeater",
            "method": "GET",
            "host": "app.example",
            "path": "/admin",
            "status": 403,
            "count": 3,
            "excerpt_json": {"length": 12, "body": "", "response_body": "denied"},
        },
        {
            "id": 2,
            "tool": "repeater",
            "method": "GET",
            "host": "app.example",
            "path": "/admin",
            "status": 200,
            "count": 1,
            "excerpt_json": {
                "length": 120,
                "body": "role=admin",
                "response_body": '{"ok":true}',
                "jwt_present": True,
            },
        },
    ]
    clusters = enrich_clusters(rows)
    assert clusters[0]["deltas"] == ["403→200", "length", "jwt"]
    assert clusters[0]["jwt_present"] is True
    assert clusters[0]["best"]["id"] == 2
    assert clusters[0]["best"]["response_body"] == '{"ok":true}'
    assert clusters[0]["scanner_event_id"] is None
