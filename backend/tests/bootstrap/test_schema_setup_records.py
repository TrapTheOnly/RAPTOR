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
    assert any("alter table records add column origin" in query for query in cursor.queries)
    assert any("alter table records add column sync_conflict" in query for query in cursor.queries)
    assert any("alter table records add column sync_conflict_reason" in query for query in cursor.queries)


def test_create_pentest_collaborators_table_creates_table():
    cursor = FakeCursor()

    schema_setup.create_pentest_collaborators_table(cursor)

    assert any("create table if not exists pentest_collaborators" in query for query in cursor.queries)
