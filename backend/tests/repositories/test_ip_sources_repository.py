import sqlite3

from app.repositories import ip_sources_repository


def _setup_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE ip_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            ip_address TEXT NOT NULL UNIQUE
        )
        """
    )
    c.execute(
        """
        CREATE TABLE records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            last_modification_date TEXT
        )
        """
    )
    c.execute(
        "INSERT INTO records (ip_address, source, status, last_modification_date) VALUES (?, ?, ?, NULL)",
        ("10.10.10.10", "Other", "unchanged"),
    )
    conn.commit()
    conn.close()


def test_add_and_delete_ip_source_updates_records(tmp_path):
    db_path = str(tmp_path / "ip.db")
    _setup_db(db_path)

    updated = ip_sources_repository.add_ip_source("Corp", "10.10.10.10", db_path=db_path)
    assert updated == 1

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT source, status FROM records WHERE ip_address = ?", ("10.10.10.10",))
    source, status = c.fetchone()
    conn.close()
    assert source == "Corp"
    assert status == "updated"

    deleted = ip_sources_repository.delete_ip_source("10.10.10.10", db_path=db_path)
    assert deleted == ("Corp", 1)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT source, status FROM records WHERE ip_address = ?", ("10.10.10.10",))
    source_after, status_after = c.fetchone()
    conn.close()
    assert source_after == "Other"
    assert status_after == "updated"
