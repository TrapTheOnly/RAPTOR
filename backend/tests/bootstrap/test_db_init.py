import sqlite3

from app.bootstrap import db_init, seed_data


def test_init_db_is_idempotent(tmp_path, monkeypatch):
    db_path = str(tmp_path / "init.db")

    monkeypatch.setattr(
        seed_data,
        "get_default_service_checklists",
        lambda: [
            {
                "key": "dns-security",
                "name": "DNS Security",
                "service": "dns",
                "source": "canonical",
                "auto_ports": [53],
                "sections": [{"name": "General", "items": [{"id": "dns-1", "testName": "test"}]}],
            }
        ],
    )
    monkeypatch.setattr(
        seed_data,
        "get_default_report_templates",
        lambda: [
            {
                "key": "default-report",
                "name": "Default Report",
                "description": "Template",
                "blocks": [{"type": "title", "text": "Report"}],
            }
        ],
    )

    db_init.init_db(db_path)
    db_init.init_db(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM app_meta WHERE key = 'service_checklists_seeded_v2'")
    assert c.fetchone()[0] == 1

    c.execute("SELECT COUNT(*) FROM app_meta WHERE key = 'report_templates_seeded_v1'")
    assert c.fetchone()[0] == 1

    c.execute("SELECT COUNT(*) FROM service_checklists")
    assert c.fetchone()[0] == 1

    c.execute("SELECT COUNT(*) FROM report_templates")
    assert c.fetchone()[0] == 1

    conn.close()
