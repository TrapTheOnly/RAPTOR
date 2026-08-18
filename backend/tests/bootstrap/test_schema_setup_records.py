from app.bootstrap import schema_setup


class FakeCursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append(" ".join(str(query).split()).lower())
        return self


def test_create_records_table_adds_manual_origin_columns(monkeypatch):
    cursor = FakeCursor()
    existing_columns = {"application_id"}
    monkeypatch.setattr(schema_setup, "get_table_columns", lambda cur, table_name: set(existing_columns))

    columns = schema_setup.create_records_table(cursor)

    assert "origin" in columns
    assert "sync_conflict" in columns
    assert "sync_conflict_reason" in columns
    assert any("create sequence if not exists records_id_seq" in query for query in cursor.queries)
    assert any("nextval('records_id_seq')" in query for query in cursor.queries)
    assert any("alter table records add column origin" in query for query in cursor.queries)
    assert any("alter table records add column sync_conflict" in query for query in cursor.queries)
    assert any("alter table records add column sync_conflict_reason" in query for query in cursor.queries)


def test_execute_ignore_exists_rolls_back_savepoint_on_duplicate():
    class _Dup(Exception):
        sqlstate = "23505"

    class _Cursor:
        def __init__(self):
            self.queries = []

        def execute(self, query, params=None):
            sql = " ".join(str(query).split())
            self.queries.append(sql)
            if sql.upper().startswith("CREATE TABLE"):
                raise _Dup("duplicate key value violates unique constraint")
            return self

    cursor = _Cursor()
    schema_setup._execute_ignore_exists(cursor, "CREATE TABLE IF NOT EXISTS records (id INTEGER)")
    joined = " | ".join(cursor.queries)
    assert "SAVEPOINT raptor_schema_obj" in joined
    assert "ROLLBACK TO SAVEPOINT raptor_schema_obj" in joined


def test_is_already_exists_detects_postgres_codes():
    class _Exc(Exception):
        def __init__(self, sqlstate):
            super().__init__("boom")
            self.sqlstate = sqlstate

    assert schema_setup._is_already_exists(_Exc("23505"))
    assert schema_setup._is_already_exists(_Exc("42P07"))
    assert schema_setup._is_already_exists(_Exc("42710"))
    assert not schema_setup._is_already_exists(_Exc("23503"))


def test_create_pentest_collaborators_table_creates_table():
    cursor = FakeCursor()

    schema_setup.create_pentest_collaborators_table(cursor)

    assert any("create table if not exists pentest_collaborators" in query for query in cursor.queries)
