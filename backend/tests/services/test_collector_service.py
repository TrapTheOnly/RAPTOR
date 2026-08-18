from datetime import datetime, timedelta, timezone

from app.services import collector_service


def test_enroll_agent_rejects_missing_hostname(monkeypatch):
    payload, status = collector_service.enroll_agent_service({"token": "raptor_enroll_x"})
    assert status == 400
    assert "hostname" in payload["error"]


def test_enroll_agent_happy_path(monkeypatch):
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(collector_service, "_utc_now", lambda: now)
    monkeypatch.setattr(collector_service, "_generate_token", lambda prefix: prefix + "secret")
    monkeypatch.setattr(
        collector_service,
        "get_enroll_token_by_hash",
        lambda token_hash: {
            "id": 3,
            "expires_at": now + timedelta(hours=1),
            "used_at": None,
            "revoked_at": None,
        },
    )
    monkeypatch.setattr(collector_service, "create_dns_source", lambda **kwargs: 12)
    created = {}
    monkeypatch.setattr(
        collector_service,
        "insert_agent",
        lambda **kwargs: created.update(kwargs) or 9,
    )
    monkeypatch.setattr(collector_service, "mark_enroll_token_used", lambda token_id: created.setdefault("used", token_id))
    monkeypatch.setattr(collector_service, "record_audit_event", lambda **kwargs: None)

    payload, status = collector_service.enroll_agent_service(
        {"token": "raptor_enroll_x", "hostname": "dns01", "agent_version": "1.0.0"}
    )

    assert status == 201
    assert payload["source_id"] == 12
    assert payload["agent_id"] == 9
    assert payload["token"].startswith("raptor_col_")
    assert created["hostname"] == "dns01"
    assert created["used"] == 3


def test_ingest_rejects_source_mismatch(monkeypatch):
    payload, status = collector_service.ingest_service(
        {"id": 1, "source_id": 12, "hostname": "dns01", "agent_version": "1"},
        {"source_id": 99, "records": [{"fqdn": "a.example", "rrtype": "A", "rdata": "1.2.3.4"}]},
    )
    assert status == 403


def test_ingest_projects_through_apply(monkeypatch):
    monkeypatch.setattr(
        collector_service,
        "apply_ingest_batch",
        lambda source_id, records, cursor=None: {
            "stored": 2,
            "projected": 1,
            "batch_id": "b1",
        },
    )
    monkeypatch.setattr(collector_service, "touch_agent_heartbeat", lambda *args, **kwargs: None)
    monkeypatch.setattr(collector_service, "record_audit_event", lambda **kwargs: None)
    monkeypatch.setattr(collector_service, "_maybe_rotate_token", lambda agent: None)

    payload, status = collector_service.ingest_service(
        {"id": 1, "source_id": 12, "hostname": "dns01", "agent_version": "1"},
        {
            "source_id": 12,
            "cursor": "2024010101",
            "zones": [
                {
                    "name": "example.com",
                    "soa_serial": "2024010101",
                    "records": [
                        {"fqdn": "www.example.com", "rrtype": "A", "rdata": "10.0.0.2"},
                        {"fqdn": "example.com", "rrtype": "MX", "rdata": "10 mail.example.com"},
                    ],
                }
            ],
        },
    )
    assert status == 200
    assert payload["stored"] == 2
    assert payload["projected"] == 1


def test_revoke_missing_collector(monkeypatch):
    monkeypatch.setattr(collector_service, "get_agent_by_id", lambda agent_id: None)
    payload, status = collector_service.revoke_collector_service(4, "awadmin")
    assert status == 404
    assert payload["error"]


def test_delete_collector_invalidates_agent(monkeypatch):
    deleted = []
    monkeypatch.setattr(
        collector_service,
        "get_agent_by_id",
        lambda agent_id: {"id": agent_id, "hostname": "dns01", "source_id": 12},
    )
    monkeypatch.setattr(collector_service, "delete_agent", lambda agent_id: deleted.append(agent_id))
    monkeypatch.setattr(collector_service, "record_audit_event", lambda **kwargs: None)
    payload, status = collector_service.delete_collector_service(9, "awadmin")
    assert status == 200
    assert deleted == [9]
    assert "key" in payload["message"].lower()


def test_rename_collector(monkeypatch):
    row = {
        "id": 3,
        "hostname": "dns01",
        "display_name": "DC1",
        "mode": "one_sided",
    }

    def _get(_id):
        return dict(row)

    def _rename(_id, display_name=None, callback_url=None):
        if display_name is not None:
            row["display_name"] = display_name
        if callback_url is not None:
            row["callback_url"] = callback_url

    monkeypatch.setattr(collector_service, "get_agent_by_id", _get)
    monkeypatch.setattr(collector_service, "update_agent_fields", _rename)
    monkeypatch.setattr(collector_service, "record_audit_event", lambda **kwargs: None)
    payload, status = collector_service.rename_collector_service(3, {"display_name": "HQ BIND"}, "awadmin")
    assert status == 200
    assert payload["agent"]["display_name"] == "HQ BIND"


def test_ping_rejects_one_sided(monkeypatch):
    monkeypatch.setattr(
        collector_service,
        "get_agent_by_id",
        lambda agent_id: {"id": agent_id, "mode": "one_sided", "callback_url": "http://dns01:7444"},
    )
    payload, status = collector_service.ping_collector_service(2)
    assert status == 400
    assert "one-sided" in payload["error"].lower()


def test_enroll_token_includes_installers(monkeypatch):
    monkeypatch.setattr(collector_service, "_utc_now", lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))
    monkeypatch.setattr(collector_service, "_generate_token", lambda prefix: prefix + "abc")
    monkeypatch.setattr(collector_service, "insert_enroll_token", lambda **kwargs: 1)
    monkeypatch.setattr(collector_service, "record_audit_event", lambda **kwargs: None)
    payload, status = collector_service.create_enroll_token_service(
        {"label": "dc01", "mode": "two-sided"},
        "awadmin",
        public_base_url="https://raptor.example",
    )
    assert status == 201
    assert "raptor-collector setup" in payload["install"]["linux"]
    assert "install.ps1" in payload["install"]["windows"]
    assert payload["mode"] == "two_sided"


def test_peer_ip_prefers_forwarded_for():
    assert collector_service.peer_ip_from_request("192.168.215.2, 10.0.0.1", "127.0.0.1") == "192.168.215.2"
    assert collector_service.peer_ip_from_request("", "192.168.107.4") == "192.168.107.4"


def test_ping_explains_unresolvable_hostname(monkeypatch):
    class FailOpener:
        def open(self, request, timeout=3):
            raise OSError("[Errno -2] Name or service not known")

    monkeypatch.setattr(
        collector_service,
        "get_agent_by_id",
        lambda agent_id: {
            "id": agent_id,
            "mode": "two_sided",
            "callback_url": "http://cf23cf485016:7444",
        },
    )
    monkeypatch.setattr(collector_service, "build_opener", lambda *args, **kwargs: FailOpener())
    payload, status = collector_service.ping_collector_service(2)
    assert status == 200
    assert payload["ok"] is False
    assert "cannot resolve hostname" in payload["error"].lower()


def test_ping_falls_back_to_last_seen_ip(monkeypatch):
    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Opener:
        def open(self, request, timeout=3):
            if "cf23cf485016" in request.full_url:
                raise OSError("[Errno -2] Name or service not known")
            if "192.168.215.2" not in request.full_url:
                raise AssertionError(request.full_url)
            return FakeResp()

    monkeypatch.setattr(
        collector_service,
        "get_agent_by_id",
        lambda agent_id: {
            "id": agent_id,
            "mode": "two_sided",
            "callback_url": "http://cf23cf485016:7444",
            "last_seen_ip": "192.168.215.2",
        },
    )
    monkeypatch.setattr(collector_service, "build_opener", lambda *args, **kwargs: Opener())
    payload, status = collector_service.ping_collector_service(2)
    assert status == 200
    assert payload["ok"] is True
    assert payload["url"] == "http://192.168.215.2:7444/healthz"


def test_update_callback_url(monkeypatch):
    row = {
        "id": 2,
        "hostname": "cf23cf485016",
        "display_name": "alpine-test-2",
        "mode": "two_sided",
        "callback_url": "http://cf23cf485016:7444",
    }

    def _get(_id):
        return dict(row)

    def _update(_id, display_name=None, callback_url=None):
        if callback_url is not None:
            row["callback_url"] = callback_url

    monkeypatch.setattr(collector_service, "get_agent_by_id", _get)
    monkeypatch.setattr(collector_service, "update_agent_fields", _update)
    monkeypatch.setattr(collector_service, "record_audit_event", lambda **kwargs: None)
    payload, status = collector_service.rename_collector_service(
        2,
        {"callback_url": "http://192.168.215.2:7444"},
        "awadmin",
    )
    assert status == 200
    assert payload["agent"]["callback_url"] == "http://192.168.215.2:7444"


def test_live_uses_interval_plus_grace(monkeypatch):
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(collector_service, "_utc_now", lambda: now)
    row = {
        "id": 1,
        "hostname": "dns01",
        "display_name": "dns01",
        "mode": "two_sided",
        "interval_seconds": 300,
        "last_seen_at": now - timedelta(seconds=330),
    }
    assert collector_service._public_agent(row)["online"] is True
    stale = {**row, "last_seen_at": now - timedelta(seconds=400)}
    assert collector_service._public_agent(stale)["online"] is False
    fallback_live = {**row, "interval_seconds": None, "last_seen_at": now - timedelta(minutes=10)}
    assert collector_service._public_agent(fallback_live)["online"] is True
    fallback_stale = {**row, "interval_seconds": None, "last_seen_at": now - timedelta(minutes=16)}
    assert collector_service._public_agent(fallback_stale)["online"] is False


def test_heartbeat_returns_collect_now(monkeypatch):
    touched = {}
    monkeypatch.setattr(
        collector_service,
        "touch_agent_heartbeat",
        lambda *args, **kwargs: touched.update(kwargs),
    )
    monkeypatch.setattr(collector_service, "consume_collect_request", lambda agent_id: True)
    monkeypatch.setattr(collector_service, "_maybe_rotate_token", lambda agent: None)
    payload, status = collector_service.heartbeat_service(
        {"id": 2, "source_id": 12, "mode": "one_sided"},
        {"agent_version": "1.1.0", "interval_seconds": 120, "zones": []},
    )
    assert status == 200
    assert payload["collect_now"] is True
    assert touched["interval_seconds"] == 120


def test_collect_now_queues_one_sided(monkeypatch):
    marked = []
    monkeypatch.setattr(
        collector_service,
        "get_agent_by_id",
        lambda agent_id: {"id": agent_id, "status": "active", "mode": "one_sided", "hostname": "dns01"},
    )
    monkeypatch.setattr(collector_service, "mark_collect_requested", lambda agent_id=None: marked.append(agent_id))
    monkeypatch.setattr(collector_service, "record_audit_event", lambda **kwargs: None)
    payload, status = collector_service.collect_now_service(4, "awadmin")
    assert status == 200
    assert payload["queued"] is True
    assert payload["immediate"] is False
    assert payload["reason"] == "one_sided"
    assert marked == [4]


def test_collect_now_posts_run_for_two_sided(monkeypatch):
    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Opener:
        def open(self, request, timeout=3):
            assert request.full_url.endswith("/run")
            assert request.get_method() == "POST"
            return FakeResp()

    monkeypatch.setattr(
        collector_service,
        "get_agent_by_id",
        lambda agent_id: {
            "id": agent_id,
            "status": "active",
            "mode": "two_sided",
            "callback_url": "http://192.168.215.2:7444",
            "hostname": "alpine",
        },
    )
    monkeypatch.setattr(collector_service, "mark_collect_requested", lambda agent_id=None: None)
    monkeypatch.setattr(collector_service, "record_audit_event", lambda **kwargs: None)
    monkeypatch.setattr(collector_service, "build_opener", lambda *args, **kwargs: Opener())
    payload, status = collector_service.collect_now_service(2, "awadmin")
    assert status == 200
    assert payload["immediate"] is True
