from app.services import engagement_namer


def test_sanitize_title_strips_quotes_and_caps_length():
    assert engagement_namer.sanitize_title('  "Hello world" \n', "fb") == "Hello world"
    assert engagement_namer.sanitize_title("", "fb") == "fb"
    assert len(engagement_namer.sanitize_title("x" * 100, "fb")) == engagement_namer.TITLE_MAX


def test_fallback_title_for_scan_and_jwt():
    assert engagement_namer.fallback_title(kind="ai_scan", host_count=3) == "AI scan · 3 hosts"
    assert engagement_namer.fallback_title(kind="ai_scan", host_count=1) == "AI scan · 1 host"
    assert engagement_namer.fallback_title(kind="jwt", host="api.example", path="/login") == (
        "JWT suite on api.example/login"
    )
    assert engagement_namer.fallback_title(kind="analyze", host_count=4) == "Burp analyze · 4 endpoints"
    assert engagement_namer.fallback_title(kind="analyze", host="app.example") == "Burp analyze on app.example"


def test_name_engagement_uses_llm_title_and_redacts_jwt(monkeypatch):
    prompts = []
    monkeypatch.setattr(
        engagement_namer,
        "_complete",
        lambda prompt, max_tokens=24: prompts.append(prompt) or "Preprod JWT on login",
    )
    token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhIn0.signature"
    title = engagement_namer.name_engagement(
        kind="jwt",
        host="api.example",
        path="/login",
        extra=f"Bearer {token} focus on none alg",
    )
    assert title == "Preprod JWT on login"
    assert token not in prompts[0]
    assert "[redacted]" in prompts[0]
    assert "none alg" in prompts[0]


def test_name_engagement_falls_back_when_llm_missing(monkeypatch):
    monkeypatch.setattr(
        engagement_namer,
        "_complete",
        lambda prompt, max_tokens=24: (_ for _ in ()).throw(RuntimeError("no llm")),
    )
    title = engagement_namer.name_engagement(kind="jwt", host="api.example")
    assert title == engagement_namer.fallback_title(kind="jwt", host="api.example")
