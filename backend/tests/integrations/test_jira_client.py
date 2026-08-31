import httpx

from app.integrations.jira.client import JiraClient, JiraError


def _client(handler) -> JiraClient:
    transport = httpx.MockTransport(handler)
    inner = httpx.Client(transport=transport, base_url="http://jira.example", headers={"Accept": "application/json"})
    return JiraClient(
        "http://jira.example",
        "token",
        email="admin@raptor.local",
        api_style="auto",
        transport=inner,
    )


def test_list_projects_uses_server_project_list_when_search_is_a_key():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/rest/api/3/project":
            return httpx.Response(404, text="<html>dead link</html>")
        if path == "/rest/api/2/project/search":
            return httpx.Response(404, json={"errorMessages": ["No project could be found with key 'search'."]})
        if path == "/rest/api/2/project":
            return httpx.Response(
                200,
                json=[
                    {"id": "10000", "key": "SEC", "name": "Security Findings"},
                    {"id": "10001", "key": "APP", "name": "Application Backlog"},
                ],
            )
        return httpx.Response(404, json={"errorMessages": ["missing"]})

    projects = _client(handler).list_projects()
    assert [item["key"] for item in projects] == ["SEC", "APP"]


def test_list_projects_prefers_cloud_search_when_plain_list_is_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/project") and "search" not in path:
            return httpx.Response(404, json={"errorMessages": ["Not found"]})
        if path.endswith("/project/search"):
            return httpx.Response(
                200,
                json={"values": [{"id": "1", "key": "PAY", "name": "Payments"}]},
            )
        return httpx.Response(404, json={})

    projects = _client(handler).list_projects()
    assert projects[0]["key"] == "PAY"


def test_list_projects_retries_when_v3_returns_login_html():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/project":
            return httpx.Response(200, text="<!DOCTYPE html><html>login</html>")
        if request.url.path == "/rest/api/2/project":
            return httpx.Response(
                200,
                json=[{"id": "10000", "key": "SEC", "name": "Security Findings"}],
            )
        return httpx.Response(404, json={})

    projects = _client(handler).list_projects()
    assert projects[0]["key"] == "SEC"


def test_list_projects_retries_when_v3_redirects_to_login():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/project":
            return httpx.Response(302, headers={"location": "/login.jsp"})
        if request.url.path == "/rest/api/2/project":
            return httpx.Response(
                200,
                json=[{"id": "10000", "key": "SEC", "name": "Security Findings"}],
            )
        return httpx.Response(404, json={})

    projects = _client(handler).list_projects()
    assert projects[0]["key"] == "SEC"


def test_non_json_success_does_not_lock_api_v3():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/myself":
            return httpx.Response(200, text="<!DOCTYPE html><html>login</html>")
        if request.url.path == "/rest/api/2/myself":
            return httpx.Response(200, json={"displayName": "Admin", "name": "admin"})
        return httpx.Response(404, json={})

    client = _client(handler)
    me = client.myself()
    assert me["name"] == "admin"
    assert client.api_style == "2"


def test_list_projects_raises_when_jira_returns_nothing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"errorMessages": ["gone"]})

    try:
        _client(handler).list_projects()
    except JiraError as exc:
        assert exc.status == 404
    else:
        raise AssertionError("expected JiraError")


def test_add_attachments_posts_multipart_with_csrf_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/issue/APP-1/attachments"):
            seen["token"] = request.headers.get("x-atlassian-token")
            seen["content_type"] = request.headers.get("content-type")
            return httpx.Response(200, json=[{"filename": "shot.png"}])
        if request.url.path.endswith("/issue") and request.method == "POST":
            return httpx.Response(201, json={"id": "1", "key": "APP-1"})
        return httpx.Response(404, json={})

    client = _client(handler)
    client.api_style = "2"
    client.add_attachments("APP-1", [("shot.png", b"png-bytes", "image/png")])
    assert seen["token"] == "no-check"
    assert "multipart/form-data" in (seen["content_type"] or "")
