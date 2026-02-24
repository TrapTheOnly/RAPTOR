from app.repositories import auth_lockout_repository as repo


class _FakeCursor:
    def __init__(self, state):
        self._state = state
        self._rows = []
        self.rowcount = 0

    def execute(self, query, params=()):
        normalized = " ".join(str(query).split()).lower()
        self.rowcount = 0

        if normalized.startswith("select failed_attempts, lockout_until_epoch from auth_lockouts"):
            key = params[0]
            row = self._state.get(key)
            self._rows = [(row["failed_attempts"], row["lockout_until_epoch"])] if row else []
            return self

        if normalized.startswith("select failed_attempts, lockout_level, lockout_until_epoch from auth_lockouts"):
            key = params[0]
            row = self._state.get(key)
            self._rows = (
                [(row["failed_attempts"], row["lockout_level"], row["lockout_until_epoch"])] if row else []
            )
            return self

        if normalized.startswith("update auth_lockouts set"):
            failed_attempts, lockout_level, lockout_until_epoch, key = params
            if key in self._state:
                self._state[key]["failed_attempts"] = failed_attempts
                self._state[key]["lockout_level"] = lockout_level
                self._state[key]["lockout_until_epoch"] = lockout_until_epoch
                self.rowcount = 1
            self._rows = []
            return self

        if normalized.startswith("insert into auth_lockouts"):
            key, failed_attempts, lockout_level, lockout_until_epoch = params
            self._state[key] = {
                "failed_attempts": failed_attempts,
                "lockout_level": lockout_level,
                "lockout_until_epoch": lockout_until_epoch,
            }
            self.rowcount = 1
            self._rows = []
            return self

        if normalized.startswith("delete from auth_lockouts where username ="):
            key = params[0]
            deleted = 1 if self._state.pop(key, None) is not None else 0
            self.rowcount = deleted
            self._rows = []
            return self

        raise AssertionError(f"Unexpected query in test fake: {query}")

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConnection:
    def __init__(self, state):
        self._state = state

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


def test_register_failed_login_attempt_locks_after_limit(monkeypatch):
    state = {}
    monkeypatch.setattr(repo, "get_db_connection", lambda _db_path: _FakeConnection(state))

    monkeypatch.setattr(repo, "FAILED_LOGIN_ATTEMPT_LIMIT", 1)
    monkeypatch.setattr(repo, "LOGIN_LOCKOUT_BASE_MINUTES", 1)
    monkeypatch.setattr(repo, "LOGIN_LOCKOUT_MAX_MINUTES", 0)

    result = repo.register_failed_login_attempt("UserA", db_path="postgresql://unit-test")
    assert result["locked"] is True
    assert result["retry_after_seconds"] >= 60

    status = repo.get_login_lockout_status("usera", db_path="postgresql://unit-test")
    assert status["locked"] is True

    repo.clear_login_lockout_state("USERA", db_path="postgresql://unit-test")
    status_after_clear = repo.get_login_lockout_status("usera", db_path="postgresql://unit-test")
    assert status_after_clear["locked"] is False
