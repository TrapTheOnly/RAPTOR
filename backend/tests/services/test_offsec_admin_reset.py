from app.services.offsec_admin_service import REQUIRED_RESET_PHRASE, reset_keep_open_vulnerabilities


def test_reset_requires_new_phrase():
    payload, status = reset_keep_open_vulnerabilities(
        {"confirm": True, "phrase": "RESET ALL BUT OPEN VULNERABILITIES"}
    )
    assert status == 400
    assert payload["error"] == "Confirmation phrase required."


def test_reset_updates_notebooks_and_does_not_delete(monkeypatch):
    executed = []

    class Cursor:
        rowcount = 4

        def execute(self, query, params=None):
            executed.append(" ".join(str(query).split()).lower())
            return self

        def fetchone(self):
            return {"n": 3}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return Cursor()

        def commit(self):
            return None

        row_factory = None

    monkeypatch.setattr("app.services.offsec_admin_service.get_db_connection", lambda _path: Conn())
    payload, status = reset_keep_open_vulnerabilities({"confirm": True, "phrase": REQUIRED_RESET_PHRASE})
    assert status == 200
    assert payload["stats"]["total_reset"] == 4
    joined = " ".join(executed)
    assert "delete from pentest_data" not in joined
    assert "delete from pentest_findings" not in joined
    assert "update pentest_data" in joined
