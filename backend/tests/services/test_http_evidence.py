from app.services.http_evidence import format_http_exchange, markdown_from_event


def test_format_http_exchange_pairs_request_and_response():
    markdown = format_http_exchange(
        method="POST",
        path="/login",
        host="example.com",
        headers={"Authorization": "Bearer [jwt]", "Content-Type": "application/json"},
        body='{"user":"ada"}',
        status=200,
        response_body='{"ok":true}',
    )
    assert markdown.startswith("```http\n")
    assert "POST /login HTTP/1.1" in markdown
    assert "Host: example.com" in markdown
    assert "\n===\n" in markdown
    assert "HTTP/1.1 200" in markdown
    assert markdown.index("POST /login") < markdown.index("===")
    assert markdown.index("===") < markdown.index("HTTP/1.1 200")
    assert '{"ok":true}' in markdown


def test_format_http_exchange_request_only_without_status():
    markdown = format_http_exchange(method="GET", path="/", host="example.com")
    assert "```http" in markdown
    assert "===" not in markdown
    assert "GET / HTTP/1.1" in markdown


def test_markdown_from_event_uses_excerpt():
    markdown = markdown_from_event(
        {
            "method": "GET",
            "host": "api.example",
            "path": "/v1/me",
            "status": 401,
            "excerpt_json": {
                "headers": {"Authorization": "[REDACTED]"},
                "body": "",
                "query": "debug=1",
            },
        }
    )
    assert "GET /v1/me?debug=1 HTTP/1.1" in markdown
    assert "Authorization: [REDACTED]" in markdown
    assert "HTTP/1.1 401" in markdown


def test_markdown_from_event_includes_response_body():
    markdown = markdown_from_event(
        {
            "method": "GET",
            "host": "api.example",
            "path": "/v1/me",
            "status": 200,
            "excerpt_json": {
                "headers": {"Accept": "*/*"},
                "body": "",
                "response_headers": {"Content-Type": "application/json"},
                "response_body": '{"id":1}',
            },
        }
    )
    assert '{"id":1}' in markdown
    assert "Content-Type: application/json" in markdown
