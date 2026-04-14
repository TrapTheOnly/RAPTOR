from app.repositories import records_mutation_repository as repo


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self._fetchone = None
        self._fetchall = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.state["queries"].append((normalized, params))

        if normalized.startswith(
            "select id, name, ip_address, source, maintainer, origin, sync_conflict from records where id ="
        ):
            self._fetchone = self.state.get("record_by_id")
        elif normalized.startswith("select id, name, ip_address, source, maintainer, origin, sync_conflict from records"):
            self._fetchall = list(self.state["records"])
        elif normalized.startswith("update records set sync_conflict = 1"):
            self.state["conflict_updates"].append(params)
        elif normalized.startswith("update records set status = 'missing'"):
            self.state["missing_updates"].append(params)
        elif normalized.startswith("insert into record_history"):
            self.state["history_writes"] += 1
        elif normalized.startswith("insert into records"):
            self._fetchone = (self.state.get("inserted_record_id", 2),)
        elif normalized.startswith("select source_name from ip_sources"):
            self._fetchone = None
        elif normalized.startswith("update records set ip_address ="):
            self.state["resolved_updates"].append(params)
        elif normalized.startswith("update pentest_data set dns_name ="):
            self.state["pentest_updates"].append(params)
        elif normalized.startswith("delete from pentest_data where record_id ="):
            self.state["pentest_deletes"].append(params)
        elif normalized.startswith("delete from records where id ="):
            self.state["record_deletes"].append(params)
        return self

    def fetchall(self):
        return self._fetchall

    def fetchone(self):
        return self._fetchone


class FakeConnection:
    def __init__(self, state):
        self.state = state
        self.cursor_obj = FakeCursor(state)
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_store_records_in_db_skips_missing_mark_for_manual_records(monkeypatch):
    state = {
        "records": [
            (1, "manual.example.com", "10.0.0.1", "Other", "ops", "manual", 0),
        ],
        "queries": [],
        "conflict_updates": [],
        "missing_updates": [],
        "history_writes": 0,
        "resolved_updates": [],
        "pentest_updates": [],
        "pentest_deletes": [],
        "record_deletes": [],
        "inserted_record_id": 2,
    }
    monkeypatch.setattr(repo, "get_db_connection", lambda db_path: FakeConnection(state))

    repo.store_records_in_db([{"name": "auto.example.com", "ip_address": "10.0.0.2", "source": "Other"}])

    assert state["missing_updates"], "Expected missing sweep to run for automated records."
    sweep_params = state["missing_updates"][0]
    assert "auto.example.com" in sweep_params


def test_store_records_in_db_marks_conflict_for_manual_import_collision(monkeypatch):
    state = {
        "records": [
            (1, "api.example.com", "10.0.0.1", "Other", "ops", "manual", 0),
        ],
        "queries": [],
        "conflict_updates": [],
        "missing_updates": [],
        "history_writes": 0,
        "resolved_updates": [],
        "pentest_updates": [],
        "pentest_deletes": [],
        "record_deletes": [],
        "inserted_record_id": 2,
    }
    monkeypatch.setattr(repo, "get_db_connection", lambda db_path: FakeConnection(state))

    repo.store_records_in_db([{"name": "api.example.com", "ip_address": "10.0.0.2", "source": "Other"}])

    assert state["conflict_updates"]
    assert state["conflict_updates"][0][0] == repo.MANUAL_SYNC_CONFLICT_REASON


def test_resolve_manual_sync_conflict_converts_record(monkeypatch):
    state = {
        "record_by_id": (3, "api.example.com", "10.0.0.1", "Other", "ops", "manual", 1),
        "queries": [],
        "conflict_updates": [],
        "missing_updates": [],
        "history_writes": 0,
        "resolved_updates": [],
        "pentest_updates": [],
        "pentest_deletes": [],
        "record_deletes": [],
        "records": [],
    }
    monkeypatch.setattr(repo, "get_db_connection", lambda db_path: FakeConnection(state))

    result = repo.resolve_manual_sync_conflict(
        record_id=3,
        imported_ip_address="10.0.0.2",
        username="admin1",
    )

    assert result is None
    assert state["resolved_updates"]
    assert state["pentest_updates"]


def test_delete_record_removes_pentest_row_before_record(monkeypatch):
    state = {
        "queries": [],
        "conflict_updates": [],
        "missing_updates": [],
        "history_writes": 0,
        "resolved_updates": [],
        "pentest_updates": [],
        "pentest_deletes": [],
        "record_deletes": [],
        "records": [],
    }

    class DeleteCursor(FakeCursor):
        def execute(self, query, params=None):
            normalized = " ".join(str(query).split()).lower()
            self.state["queries"].append((normalized, params))
            if normalized.startswith("select ip_address, source, maintainer from records where id ="):
                self._fetchone = ("10.0.0.1", "Other", "ops")
            elif normalized.startswith("insert into record_history"):
                self.state["history_writes"] += 1
            elif normalized.startswith("delete from pentest_data where record_id ="):
                self.state["pentest_deletes"].append(params)
            elif normalized.startswith("delete from records where id ="):
                self.state["record_deletes"].append(params)
            return self

    class DeleteConnection(FakeConnection):
        def __init__(self, inner_state):
            self.state = inner_state
            self.cursor_obj = DeleteCursor(inner_state)
            self.committed = False
            self.closed = False

    monkeypatch.setattr(repo, "get_db_connection", lambda db_path: DeleteConnection(state))

    deleted = repo.delete_record(5, "admin1")

    assert deleted is True
    assert state["pentest_deletes"] == [(5,)]
    assert state["record_deletes"] == [(5,)]
    pentest_delete_index = next(
        idx for idx, (query, _) in enumerate(state["queries"]) if query.startswith("delete from pentest_data")
    )
    record_delete_index = next(
        idx for idx, (query, _) in enumerate(state["queries"]) if query.startswith("delete from records")
    )
    assert pentest_delete_index < record_delete_index
