from app.repositories import users_repository


class FakeCursor:
    def __init__(self):
        self.queries = []
        self.rowcount = 1

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.queries.append((normalized, params))
        if normalized.startswith("update allowed_users"):
            self.rowcount = 1
        return self


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_update_user_role_removes_collaborations_for_non_pentest_roles(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(users_repository, "get_db_connection", lambda db_path: conn)

    rowcount = users_repository.update_user_role("alice", "user", "[]")

    assert rowcount == 1
    assert any(query.startswith("update allowed_users set role = ?, permissions = ?") for query, _ in conn.cursor_obj.queries)
    assert any(query.startswith("delete from pentest_collaborators where username = ?") for query, _ in conn.cursor_obj.queries)
    assert conn.committed is True
    assert conn.closed is True


def test_update_user_role_keeps_collaborations_for_pentest_roles(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(users_repository, "get_db_connection", lambda db_path: conn)

    users_repository.update_user_role("alice", "pentester", "[]")

    assert not any(query.startswith("delete from pentest_collaborators where username = ?") for query, _ in conn.cursor_obj.queries)
