import sqlite3

from app.repositories import auth_lockout_repository as repo


def _setup_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE auth_lockouts (
            username TEXT PRIMARY KEY,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            lockout_level INTEGER NOT NULL DEFAULT 0,
            lockout_until_epoch INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def test_register_failed_login_attempt_locks_after_limit(tmp_path, monkeypatch):
    db_path = str(tmp_path / "lockouts.db")
    _setup_db(db_path)

    monkeypatch.setattr(repo, "FAILED_LOGIN_ATTEMPT_LIMIT", 1)
    monkeypatch.setattr(repo, "LOGIN_LOCKOUT_BASE_MINUTES", 1)
    monkeypatch.setattr(repo, "LOGIN_LOCKOUT_MAX_MINUTES", 0)

    result = repo.register_failed_login_attempt("UserA", db_path=db_path)
    assert result["locked"] is True
    assert result["retry_after_seconds"] >= 60

    status = repo.get_login_lockout_status("usera", db_path=db_path)
    assert status["locked"] is True

    repo.clear_login_lockout_state("USERA", db_path=db_path)
    status_after_clear = repo.get_login_lockout_status("usera", db_path=db_path)
    assert status_after_clear["locked"] is False
