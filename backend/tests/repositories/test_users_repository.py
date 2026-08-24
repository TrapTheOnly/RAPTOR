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


class AllowlistCursor:
    def __init__(self, rows_by_query):
        self.rows_by_query = rows_by_query
        self.executed = []
        self._row = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.executed.append((normalized, params))
        self._row = None
        for needle, row in self.rows_by_query:
            if needle in normalized:
                self._row = row
                break
        return self

    def fetchone(self):
        return self._row


class AllowlistConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def cursor(self):
        return self.cursor_obj

    def close(self):
        return None


def test_find_sso_allowlist_matches_username_not_email(monkeypatch):
    alice = ("alice", "alice@corp.com", "user", "oidc", 0, "kc-1", "[]")
    cursor = AllowlistCursor([("where username = ?", alice)])
    monkeypatch.setattr(users_repository, "get_db_connection", lambda db_path: AllowlistConnection(cursor))
    row = users_repository.find_sso_allowlist("alice", email="alice@corp.com")
    assert row["username"] == "alice"
    assert row["keycloak_id"] == "kc-1"
    assert all("lower(email)" not in query for query, _ in cursor.executed)


def test_find_sso_allowlist_ignores_email_only(monkeypatch):
    cursor = AllowlistCursor(
        [
            ("where lower(email)", ("alice", "alice@corp.com", "user", "oidc", 0, "kc-1", "[]")),
        ]
    )
    monkeypatch.setattr(users_repository, "get_db_connection", lambda db_path: AllowlistConnection(cursor))
    assert users_repository.find_sso_allowlist("", email="alice@corp.com") is None
    assert cursor.executed == []


def test_find_sso_allowlist_matches_stored_subject(monkeypatch):
    alice = ("alice", "alice@corp.com", "user", "saml", 0, "kc-stable", "[]")
    cursor = AllowlistCursor([("where keycloak_id = ?", alice)])
    monkeypatch.setattr(users_repository, "get_db_connection", lambda db_path: AllowlistConnection(cursor))
    row = users_repository.find_sso_allowlist("other-name", keycloak_id="kc-stable")
    assert row["username"] == "alice"
    assert row["auth_type"] == "saml"
