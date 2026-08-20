from app.repositories import records_query_repository as repo


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self._fetchall = []
        self._fetchone = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.state["queries"].append(normalized)
        if "information_schema.columns" in normalized:
            table = (params or ("",))[0]
            self._fetchall = [{"column_name": name} for name in self.state["columns"].get(table, [])]
        elif "from records r" in normalized and "pentest_data" not in normalized and "applications" not in normalized:
            self._fetchall = list(self.state["records"])
        elif "from records r" in normalized and "pentest_data" in normalized:
            self._fetchall = list(self.state["pentest_records"])
        elif "from ip_sources" in normalized:
            self._fetchall = list(self.state["ip_sources"])
        elif "from pentest_findings" in normalized and "applications" not in normalized:
            self._fetchall = list(self.state["findings"])
        elif "from applications" in normalized:
            self._fetchall = list(self.state["applications"])
        else:
            self._fetchall = []
        return self

    def fetchall(self):
        return self._fetchall

    def fetchone(self):
        return self._fetchone


class FakeConnection:
    def __init__(self, state):
        self.state = state
        self.row_factory = None
        self.cursor_obj = FakeCursor(state)

    def cursor(self):
        return self.cursor_obj

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


def test_fetch_dashboard_data_includes_findings_summary_and_applications(monkeypatch):
    state = {
        "queries": [],
        "columns": {
            "records": ["id", "name", "application_id", "in_scope", "status"],
            "pentest_findings": ["id", "title", "status", "base_score", "application_id", "created_at", "updated_at"],
            "applications": ["id", "name"],
        },
        "records": [{"id": 1, "name": "api.example.com", "source": "Other", "status": "ok", "origin": "manual", "sync_conflict": 0, "last_modification_date": None, "application_id": 9}],
        "pentest_records": [{"recordId": 1, "name": "api.example.com", "source": "Other", "applicationId": 9, "status": "In Progress", "vulnerable": 1, "vulnerability_fixed": 0, "finding_count": 1, "tested_by": "", "test_start_date": "2026-08-01", "test_end_date": None}],
        "ip_sources": [{"source_name": "corp"}],
        "findings": [
            {
                "id": "f1",
                "title": "SQLi",
                "status": "open",
                "base_score": 9.1,
                "application_id": 9,
                "created_at": "2026-08-18T00:00:00+00:00",
                "updated_at": "2026-08-18T00:00:00+00:00",
            }
        ],
        "applications": [{"id": 9, "name": "Payments", "in_scope_count": 4, "started_count": 1, "open_finding_count": 1}],
    }
    monkeypatch.setattr(repo, "get_db_connection", lambda db_path=None: FakeConnection(state))

    payload = repo.fetch_dashboard_data()

    assert payload["records"][0]["name"] == "api.example.com"
    assert payload["ipSources"][0]["source_name"] == "corp"
    assert payload["findingsSummary"]["open"] == 1
    assert payload["findingsSummary"]["bySeverity"]["critical"] == 1
    assert payload["findingsSummary"]["weekly"]
    assert payload["applications"][0]["name"] == "Payments"
    assert any("pentest_findings" in query for query in state["queries"])
