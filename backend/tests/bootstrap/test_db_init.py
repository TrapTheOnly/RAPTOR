from app.bootstrap import db_init


class _DummyCursor:
    def execute(self, query, params=None):
        return self

    def fetchone(self):
        return (True,)

    def fetchall(self):
        return []


class _DummyConnection:
    def __init__(self):
        self.commit_count = 0
        self.close_count = 0
        self._cursor = _DummyCursor()

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        return None

    def close(self):
        self.close_count += 1


def test_init_db_is_idempotent(monkeypatch):
    created_connections = []
    call_counts = {}

    def _track(name):
        def _fn(*args, **kwargs):
            call_counts[name] = call_counts.get(name, 0) + 1
        return _fn

    monkeypatch.setattr(db_init, "run_migrations", _track("run_migrations"))
    monkeypatch.setattr(db_init, "run_seed_routines", _track("run_seed_routines"))

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
    assert call_counts["run_migrations"] == 2
    assert call_counts["run_seed_routines"] == 2
