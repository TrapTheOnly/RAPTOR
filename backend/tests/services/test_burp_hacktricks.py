from app.services import burp_hacktricks


def test_search_hacktricks_returns_jwt_passages():
    hits = burp_hacktricks.search_hacktricks("jwt none alg key confusion", limit=5)
    assert hits
    assert any("jwt" in item["path"].lower() or "jwt" in item["text"].lower() for item in hits)
    assert len(hits) <= 5


def test_search_hacktricks_empty_query():
    assert burp_hacktricks.search_hacktricks("") == []
