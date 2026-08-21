import types

from app.bootstrap import migration_runner


class _FakeCursor:
    def __init__(self, tables=None, applied=None):
        self._tables = set(tables or [])
        self._applied = set(applied or [])
        self.executed = []
        self._created_table = False

    def execute(self, query, params=None):
        self.executed.append((query, params))
        return self

    def fetchone(self):
        last_query = self.executed[-1][0] if self.executed else ""
        if "information_schema.tables" in last_query:
            if "records" in self._tables:
                return (1,)
            return None
        return None

    def fetchall(self):
        last_query = self.executed[-1][0] if self.executed else ""
        if "SELECT version FROM schema_migrations" in last_query:
            return [(v,) for v in sorted(self._applied)]
        return []


def _make_migration_module(name, called):
    mod = types.ModuleType(name)

    def up(cursor):
        called.append(name)

    mod.up = up
    return mod


def test_ensure_migration_table(monkeypatch):
    cursor = _FakeCursor()
    migration_runner.ensure_migration_table(cursor)
    assert any("schema_migrations" in q for q, _ in cursor.executed)


def test_get_applied_versions(monkeypatch):
    cursor = _FakeCursor(applied=["0001_baseline", "0002_foo"])
    migration_runner.ensure_migration_table(cursor)
    versions = migration_runner.get_applied_versions(cursor)
    assert versions == {"0001_baseline", "0002_foo"}


def test_discover_migrations():
    migrations = migration_runner.discover_migrations()
    assert len(migrations) >= 1
    names = [name for name, _ in migrations]
    assert "0001_baseline" in names
    assert "0010_collector_agents" in names
    assert "0011_collector_agent_ops" in names
    assert "0013_collector_interval_collect" in names
    assert "0014_environments" in names
    assert "0015_finding_occurrences" in names
    assert "0016_report_exports" in names
    assert "0017_phase2b" in names
    assert "0018_wave_finding_workspace" in names
    assert "0019_wave_live_hosts" in names
    assert "0020_wave_started_at" in names
    assert "0021_occurrence_status_changed_at" in names
    assert "0022_cloud_dns" in names
    assert "0023_keycloak_identity_cache" in names
    assert "0025_scan_jobs" in names
    assert "0026_disable_bind_file" in names
    assert "0028_dns_source_delete_set_null" in names
    assert names == sorted(names)


def test_discover_migrations_sorted_order():
    migrations = migration_runner.discover_migrations()
    names = [name for name, _ in migrations]
    assert names == sorted(names)


def test_run_migrations_fresh_db(monkeypatch):
    called = []
    fake_baseline = _make_migration_module("0001_baseline", called)

    monkeypatch.setattr(
        migration_runner,
        "discover_migrations",
        lambda: [("0001_baseline", fake_baseline)],
    )

    cursor = _FakeCursor(tables=[], applied=[])
    migration_runner.run_migrations(cursor)

    assert "0001_baseline" in called
    inserts = [q for q, _ in cursor.executed if "INSERT INTO schema_migrations" in q]
    assert len(inserts) == 1


def test_run_migrations_existing_db_marks_baseline(monkeypatch):
    called = []
    fake_baseline = _make_migration_module("0001_baseline", called)

    monkeypatch.setattr(
        migration_runner,
        "discover_migrations",
        lambda: [("0001_baseline", fake_baseline)],
    )

    cursor = _FakeCursor(tables=["records"], applied=[])
    migration_runner.run_migrations(cursor)

    assert "0001_baseline" not in called
    inserts = [
        (q, p)
        for q, p in cursor.executed
        if "INSERT INTO schema_migrations" in q
    ]
    assert len(inserts) == 1
    assert inserts[0][1] == ("0001_baseline",)


def test_run_migrations_skips_already_applied(monkeypatch):
    called = []
    fake_baseline = _make_migration_module("0001_baseline", called)
    fake_second = _make_migration_module("0002_notifications", called)

    monkeypatch.setattr(
        migration_runner,
        "discover_migrations",
        lambda: [("0001_baseline", fake_baseline), ("0002_notifications", fake_second)],
    )

    cursor = _FakeCursor(tables=["records"], applied=["0001_baseline"])
    migration_runner.run_migrations(cursor)

    assert "0001_baseline" not in called
    assert "0002_notifications" in called


def test_run_migrations_no_pending(monkeypatch):
    monkeypatch.setattr(
        migration_runner,
        "discover_migrations",
        lambda: [("0001_baseline", _make_migration_module("0001_baseline", []))],
    )

    cursor = _FakeCursor(tables=["records"], applied=["0001_baseline"])
    migration_runner.run_migrations(cursor)

    inserts = [q for q, _ in cursor.executed if "INSERT INTO schema_migrations" in q]
    assert len(inserts) == 0


def test_run_migrations_multiple_pending_in_order(monkeypatch):
    called = []
    mods = [
        ("0001_baseline", _make_migration_module("0001_baseline", called)),
        ("0002_alpha", _make_migration_module("0002_alpha", called)),
        ("0003_beta", _make_migration_module("0003_beta", called)),
    ]

    monkeypatch.setattr(migration_runner, "discover_migrations", lambda: mods)

    cursor = _FakeCursor(tables=[], applied=[])
    migration_runner.run_migrations(cursor)

    assert called == ["0001_baseline", "0002_alpha", "0003_beta"]
