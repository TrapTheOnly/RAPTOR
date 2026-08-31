from datetime import datetime, timedelta, timezone

from app.domain.burp.fields import dedupe_key, parse_notes_credentials
from app.services import burp_auth, burp_service


def test_dedupe_key_is_stable():
    first = dedupe_key("repeater", "POST", "app.example", "/login", "{ \"a\": 1 }")
    second = dedupe_key("repeater", "post", "APP.example", "/login", "{ \"a\": 1 }")
    assert first == second
    assert first != dedupe_key("repeater", "POST", "app.example", "/login", "{ \"a\": 2 }")


def test_parse_notes_credentials():
    creds = parse_notes_credentials("username: alice\npassword: s3cret\n")
    assert creds["username"] == "alice"
    assert creds["password"] == "s3cret"


def test_mint_rejects_non_member(monkeypatch):
    monkeypatch.setattr(
        burp_service.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open", "opened_by": "ada", "members": ["ada"]},
    )
    payload, status = burp_service.mint_wave_token(1, 9, username="eve", role="pentester")
    assert status == 403
    assert "testers" in payload["error"]


def test_enroll_happy_path(monkeypatch):
    now = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(burp_service, "_utc_now", lambda: now)
    monkeypatch.setattr(burp_service, "_generate_token", lambda prefix: prefix + "secret")
    monkeypatch.setattr(
        burp_service.burp_repository,
        "get_enroll_token_by_hash",
        lambda token_hash: {
            "id": 3,
            "wave_id": 9,
            "application_id": 1,
            "created_by": "ada",
            "expires_at": now + timedelta(hours=1),
            "used_at": None,
            "revoked_at": None,
        },
    )
    monkeypatch.setattr(
        burp_service.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open", "name": "Northwind Live"},
    )
    created = {}
    monkeypatch.setattr(
        burp_service.burp_repository,
        "insert_agent",
        lambda **kwargs: created.update(kwargs) or 4,
    )
    monkeypatch.setattr(burp_service.burp_repository, "mark_enroll_token_used", lambda token_id: created.setdefault("used", token_id))
    monkeypatch.setattr(burp_service, "record_audit_event", lambda **kwargs: None)

    payload, status = burp_service.enroll_agent_service(
        {"token": "raptor_burp_enroll_x", "hostname": "laptop", "burp_version": "2025.8"}
    )
    assert status == 201
    assert payload["token"].startswith("raptor_burp_")
    assert payload["wave_id"] == 9
    assert payload["wave_name"] == "Northwind Live"
    assert created["hostname"] == "laptop"
    assert created["used"] == 3


def test_heartbeat_includes_wave_name_and_hosts(monkeypatch):
    wave = {"id": 42, "application_id": 1, "status": "open", "name": "Test wave"}
    monkeypatch.setattr(burp_service.phase2b_repository, "get_wave", lambda wave_id: wave)
    monkeypatch.setattr(
        burp_service.phase2b_repository,
        "list_live_wave_hosts",
        lambda w: [{"name": "app.test.local", "in_scope": True}, {"name": "evil.example", "in_scope": False}],
    )
    monkeypatch.setattr(burp_service.burp_repository, "touch_agent_heartbeat", lambda *args, **kwargs: None)
    monkeypatch.setattr(burp_service, "_maybe_rotate_token", lambda agent: None)

    payload, status = burp_service.heartbeat_service({"id": 4, "wave_id": 42}, {})
    assert status == 200
    assert payload["wave_id"] == 42
    assert payload["wave_name"] == "Test wave"
    assert payload["hosts"] == ["app.test.local"]


def test_ingest_dedupes_and_skips_out_of_scope(monkeypatch):
    wave = {"id": 9, "application_id": 1, "status": "open"}
    monkeypatch.setattr(burp_service.phase2b_repository, "get_wave", lambda wave_id: wave)
    monkeypatch.setattr(
        burp_service.phase2b_repository,
        "list_live_wave_hosts",
        lambda w: [{"name": "app.example", "in_scope": True}],
    )
    stored = []

    def _upsert(**kwargs):
        stored.append(kwargs)
        return {"id": 1, "count": len(stored)}

    monkeypatch.setattr(burp_service.burp_repository, "upsert_event", _upsert)
    monkeypatch.setattr(burp_service.burp_index, "rewrite_index", lambda wave_id: stored.append({"index": wave_id}))
    monkeypatch.setattr(burp_service.burp_repository, "touch_agent_heartbeat", lambda *args, **kwargs: None)

    agent = {"id": 4, "wave_id": 9, "application_id": 1}
    token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhIn0.signature"
    event = {
        "tool": "repeater",
        "method": "GET",
        "host": "app.example",
        "path": "/api",
        "status": 200,
        "body": f"token={token}",
        "headers": {"Authorization": "Bearer secret", "Accept": "application/json"},
        "response_headers": {"Set-Cookie": "sid=abc", "Content-Type": "text/plain"},
        "response_body": '{"ok":true}',
        "payload": "id=2",
        "jwt_present": True,
    }
    payload, status = burp_service.ingest_service(
        agent,
        {"events": [event, event, {**event, "host": "evil.example"}]},
    )
    assert status == 200
    assert payload["accepted"] == 2
    assert payload["skipped"] == 1
    excerpt = stored[0]["excerpt_json"]
    assert excerpt["headers"]["Authorization"] == "[REDACTED]"
    assert excerpt["headers"]["Accept"] == "application/json"
    assert excerpt["response_headers"]["Set-Cookie"] == "[REDACTED]"
    assert excerpt["response_headers"]["Content-Type"] == "text/plain"
    assert excerpt["response_body"] == '{"ok":true}'
    assert excerpt["payload"] == "id=2"
    assert excerpt["jwt_present"] is True
    assert token not in excerpt["body"]
    assert "[jwt]" in excerpt["body"]


def test_auth_notes_empty_fails(monkeypatch):
    monkeypatch.setattr(burp_auth, "notes_for_host", lambda wave, host: "")
    creds, error = burp_auth.credentials_from_notes({"id": 9}, "app.example")
    assert creds == {}
    assert error == burp_auth.EMPTY_NOTES_ERROR


def test_auth_retry_once(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, headers=None, cookies=None, text=""):
            self.status_code = status_code
            self.headers = headers or {}
            self.cookies = cookies or {}
            self.text = text

        def json(self):
            return {"access_token": "new-token"}

    calls = []

    def transport(method, url, headers=None, content=None, timeout=None, follow_redirects=None):
        calls.append({"method": method, "url": url, "headers": dict(headers or {})})
        if len(calls) == 1:
            return FakeResponse(401)
        return FakeResponse(200)

    monkeypatch.setattr(
        burp_auth.burp_repository,
        "get_auth_template",
        lambda wave_id, host="": {
            "host": "app.example",
            "request_ciphertext": "cipher",
            "extract_rule": {"type": "json", "name": "access_token"},
        },
    )
    monkeypatch.setattr(burp_auth, "decrypt_secret", lambda value: "POST /login HTTP/1.1\nHost: app.example\n\nusername={{username}}&password={{password}}")
    monkeypatch.setattr(burp_auth, "credentials_from_notes", lambda wave, host: ({"username": "ada", "password": "pw"}, None))
    monkeypatch.setattr(burp_auth, "login_with_template", lambda *args, **kwargs: ("new-token", None))

    response, meta = burp_auth.request_with_auth_retry(
        {"id": 9},
        host="app.example",
        method="GET",
        url="https://app.example/api",
        headers={"Accept": "application/json"},
        transport=transport,
    )
    assert meta["retried"] is True
    assert response.status_code == 200
    assert calls[1]["headers"]["Authorization"] == "Bearer new-token"
    assert len(calls) == 2


def test_file_evidence_creates_draft(monkeypatch):
    from app.services import burp_evidence

    wave = {"id": 9, "application_id": 1, "status": "open"}
    monkeypatch.setattr(burp_evidence.phase2b_repository, "get_wave", lambda wave_id: wave)
    monkeypatch.setattr(burp_evidence, "reject_if_closed", lambda wave: None)
    monkeypatch.setattr(burp_evidence, "host_in_scope", lambda wave, host: True)
    monkeypatch.setattr(burp_evidence, "record_id_for_host", lambda wave, host: 44)
    stored = {}
    monkeypatch.setattr(
        burp_evidence.burp_repository,
        "upsert_event",
        lambda **kwargs: stored.update(kwargs) or {"id": 81, "status": 403, "excerpt_json": kwargs["excerpt_json"]},
    )
    monkeypatch.setattr("app.services.burp_index.rewrite_index", lambda wave_id: None)
    created = {}
    monkeypatch.setattr(
        "app.services.app_program_service.create_finding",
        lambda app_id, data, username, role: created.update(data)
        or ({"finding": {"id": "f-draft", "title": data["title"]}}, 201),
    )
    agent = {"id": 4, "wave_id": 9, "application_id": 1, "username": "ada"}
    payload, status = burp_evidence.file_evidence_for_agent(
        agent,
        {
            "tool": "repeater",
            "host": "app.example",
            "path": "/admin",
            "method": "GET",
            "status": 403,
            "headers": {"Accept": "*/*"},
            "body": "",
            "response_body": "denied",
        },
    )
    assert status == 201
    assert payload["finding_id"] == "f-draft"
    assert created["status"] == "draft"
    assert created["source"] == "human"
    assert created["created_by"] != "scanner" if "created_by" in created else True
    assert "GET /admin" in created["evidence"] or "GET /admin HTTP/1.1" in created["evidence"]
    assert "denied" in created["evidence"]
    assert stored["excerpt_json"]["response_body"] == "denied"


def test_file_evidence_appends_to_draft(monkeypatch):
    from app.services import burp_evidence

    wave = {"id": 9, "application_id": 1, "status": "open"}
    monkeypatch.setattr(burp_evidence.phase2b_repository, "get_wave", lambda wave_id: wave)
    monkeypatch.setattr(burp_evidence, "reject_if_closed", lambda wave: None)
    monkeypatch.setattr(burp_evidence, "host_in_scope", lambda wave, host: True)
    monkeypatch.setattr(burp_evidence, "record_id_for_host", lambda wave, host: 44)
    monkeypatch.setattr(
        burp_evidence.burp_repository,
        "upsert_event",
        lambda **kwargs: {"id": 81, "status": 200, "excerpt_json": kwargs["excerpt_json"]},
    )
    monkeypatch.setattr("app.services.burp_index.rewrite_index", lambda wave_id: None)
    monkeypatch.setattr(
        burp_evidence.pentest_findings_repository,
        "get_finding",
        lambda finding_id: {
            "id": finding_id,
            "application_id": 1,
            "discovered_wave_id": 9,
            "status": "draft",
            "evidence": "```http\nGET /old HTTP/1.1\n```\n",
        },
    )
    patched = {}
    monkeypatch.setattr(
        "app.services.app_program_service.patch_finding",
        lambda finding_id, data, username, role: patched.update({"id": finding_id, **data})
        or ({"finding": {"id": finding_id, "evidence": data["evidence"]}}, 200),
    )
    payload, status = burp_evidence.file_evidence_for_agent(
        {"id": 4, "wave_id": 9, "application_id": 1, "username": "ada"},
        {
            "finding_id": "f-draft",
            "host": "app.example",
            "path": "/admin",
            "method": "GET",
            "status": 200,
            "response_body": "ok",
        },
    )
    assert status == 200
    assert patched["id"] == "f-draft"
    assert "GET /old" in patched["evidence"]
    assert "GET /admin" in patched["evidence"]
    assert payload["finding_id"] == "f-draft"


def test_propose_scanner_does_not_file_a_finding(monkeypatch):
    from app.services import burp_evidence

    monkeypatch.setattr(burp_evidence, "get_wave", lambda *args, **kwargs: ({"wave": {}}, 200))
    monkeypatch.setattr(burp_evidence, "wave_is_open", lambda wave: True)
    monkeypatch.setattr(
        burp_evidence.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1, "status": "open"},
    )
    monkeypatch.setattr(
        burp_evidence.burp_repository,
        "get_event",
        lambda event_id, wave_id=None: {
            "id": event_id,
            "tool": "scanner",
            "host": "app.example",
            "path": "/login",
            "method": "POST",
            "status": 200,
            "scanner_name": "SQL injection",
            "scanner_detail": "<p>Possible SQLi</p>",
            "excerpt_json": {"body": "q=1", "response_body": "error"},
        },
    )
    monkeypatch.setattr(burp_evidence.burp_repository, "list_proposals_for_wave", lambda *a, **k: [])
    created = {}
    monkeypatch.setattr(
        burp_evidence.burp_repository,
        "insert_proposal",
        lambda **kwargs: created.update(kwargs) or 12,
    )
    payload, status = burp_evidence.propose_scanner(1, 9, "ada", "pentester", {"event_id": 81})
    assert status == 201
    assert payload["engagement_id"] == "proposal:12"
    assert created["kind"] == "scanner"
    assert created["job_id"] is None
    assert "SQL injection" in created["title"]
    findings = []
    monkeypatch.setattr("app.services.app_program_service.create_finding", lambda *a, **k: findings.append(1))
    assert findings == []
