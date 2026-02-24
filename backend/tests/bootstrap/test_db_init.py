from app.bootstrap import db_init


class _DummyCursor:
    pass


class _DummyConnection:
    def __init__(self):
        self.commit_count = 0
        self.close_count = 0
        self._cursor = _DummyCursor()

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commit_count += 1

    def close(self):
        self.close_count += 1


def test_init_db_is_idempotent(monkeypatch):
    created_connections = []
    call_counts = {}

    def _track(name):
        call_counts[name] = call_counts.get(name, 0) + 1

    def _create_records_table(cursor):
        _track("create_records_table")
        return {"application_id"}

    monkeypatch.setattr(db_init, "create_records_table", _create_records_table)
    monkeypatch.setattr(db_init, "create_allowed_users_table", lambda cursor: _track("create_allowed_users_table"))
    monkeypatch.setattr(db_init, "create_applications_table", lambda cursor: _track("create_applications_table"))
    monkeypatch.setattr(
        db_init,
        "repair_legacy_application_mapping",
        lambda cursor, record_columns: _track("repair_legacy_application_mapping"),
    )
    monkeypatch.setattr(db_init, "create_ip_sources_table", lambda cursor: _track("create_ip_sources_table"))
    monkeypatch.setattr(db_init, "create_record_history_table", lambda cursor: _track("create_record_history_table"))
    monkeypatch.setattr(db_init, "create_pentest_table", lambda cursor: _track("create_pentest_table"))
    monkeypatch.setattr(db_init, "create_service_checklists_table", lambda cursor: _track("create_service_checklists_table"))
    monkeypatch.setattr(db_init, "create_report_templates_table", lambda cursor: _track("create_report_templates_table"))
    monkeypatch.setattr(db_init, "create_app_meta_table", lambda cursor: _track("create_app_meta_table"))
    monkeypatch.setattr(db_init, "create_auth_lockout_table", lambda cursor: _track("create_auth_lockout_table"))
    monkeypatch.setattr(db_init, "run_seed_routines", lambda cursor: _track("run_seed_routines"))

    def _fake_get_db_connection(_):
        conn = _DummyConnection()
        created_connections.append(conn)
        return conn

    monkeypatch.setattr(db_init, "get_db_connection", _fake_get_db_connection)

    db_init.init_db("postgresql://unit-test-1")
    db_init.init_db("postgresql://unit-test-2")

    assert len(created_connections) == 2
    assert all(conn.commit_count == 1 for conn in created_connections)
    assert all(conn.close_count == 1 for conn in created_connections)
    assert call_counts["create_records_table"] == 2
    assert call_counts["run_seed_routines"] == 2
