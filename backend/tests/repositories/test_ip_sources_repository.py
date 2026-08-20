from app.repositories import ip_sources_repository


class _FakeCursor:
    def __init__(self, state):
        self._state = state
        self._rows = []
        self.rowcount = 0

    def execute(self, query, params=()):
        normalized = " ".join(str(query).split()).lower()
        self.rowcount = 0

        if normalized.startswith("insert into ip_sources"):
            source_name, ip_address = params
            self._state["ip_sources"][ip_address] = source_name
            self.rowcount = 1
            self._rows = []
            return self

        if normalized.startswith("update records set source = ?"):
            source_name, ip_address = params
            updated = 0
            for row in self._state["records"]:
                if row["ip_address"] == ip_address:
                    row["source"] = source_name
                    row["status"] = "updated"
                    updated += 1
            self.rowcount = updated
            self._rows = []
            return self

        if normalized.startswith("select source_name from ip_sources where ip_address ="):
            ip_address = params[0]
            source = self._state["ip_sources"].get(ip_address)
            self._rows = [(source,)] if source is not None else []
            return self

        if normalized.startswith("delete from ip_sources where ip_address ="):
            ip_address = params[0]
            deleted = 1 if self._state["ip_sources"].pop(ip_address, None) is not None else 0
            self.rowcount = deleted
            self._rows = []
            return self

        if normalized.startswith("update records set source = 'other'"):
            ip_address = params[0]
            updated = 0
            for row in self._state["records"]:
                if row["ip_address"] == ip_address:
                    row["source"] = "Other"
                    row["status"] = "updated"
                    updated += 1
            self.rowcount = updated
            self._rows = []
            return self

        if normalized.startswith("select id, source_name, ip_address from ip_sources"):
            self._rows = [
                {"id": index + 1, "source_name": source_name, "ip_address": ip_address}
                for index, (ip_address, source_name) in enumerate(self._state["ip_sources"].items())
            ]
            return self

        raise AssertionError(f"Unexpected query in test fake: {query}")

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeConnection:
    def __init__(self, state):
        self._state = state
        self.row_factory = None

    def cursor(self):
        return _FakeCursor(self._state)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_add_and_delete_ip_source_updates_records(monkeypatch):
    state = {
        "ip_sources": {},
        "records": [{"ip_address": "10.10.10.10", "source": "Other", "status": "unchanged"}],
    }
    monkeypatch.setattr(ip_sources_repository, "get_db_connection", lambda _db_path: _FakeConnection(state))

    updated = ip_sources_repository.add_ip_source("Corp", "10.10.10.10", db_path="postgresql://unit-test")
    assert updated == 1
    assert state["records"][0]["source"] == "Corp"
    assert state["records"][0]["status"] == "updated"

    deleted = ip_sources_repository.delete_ip_source("10.10.10.10", db_path="postgresql://unit-test")
    assert deleted == ("Corp", 1)
    assert state["records"][0]["source"] == "Other"
    assert state["records"][0]["status"] == "updated"


def test_ensure_ip_sources_upserts_provider_group(monkeypatch):
    state = {
        "ip_sources": {"1.1.1.1": "Corp"},
        "records": [],
    }
    monkeypatch.setattr(ip_sources_repository, "get_db_connection", lambda _db_path: _FakeConnection(state))

    written = ip_sources_repository.ensure_ip_sources(
        "Cloudflare",
        ["1.1.1.1", " 1.1.1.1 ", "8.8.8.8", ""],
        db_path="postgresql://unit-test",
    )
    assert written == 2
    assert state["ip_sources"]["1.1.1.1"] == "Cloudflare"
    assert state["ip_sources"]["8.8.8.8"] == "Cloudflare"
    assert ip_sources_repository.ip_source_name_for_dns_type("route53") == "AWS"
    assert ip_sources_repository.ip_source_name_for_dns_type("bind_agent") is None
