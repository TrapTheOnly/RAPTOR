import httpx

from app.integrations.defectdojo.client import DefectDojoClient, DefectDojoError


def _client(handler) -> DefectDojoClient:
    transport = httpx.MockTransport(handler)
    inner = httpx.Client(transport=transport, base_url="http://dojo.example", headers={"Accept": "application/json"})
    return DefectDojoClient("http://dojo.example", "token", transport=inner)


def test_myself_prefers_user_profile():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.rstrip("/") == "/api/v2/user_profile":
            return httpx.Response(200, json={"user": {"id": 1, "username": "admin"}})
        return httpx.Response(500, json={"detail": "unexpected " + request.url.path})

    me = _client(handler).myself()
    assert me["id"] == 1
    assert me["username"] == "admin"


def test_myself_falls_back_when_users_me_is_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.rstrip("/")
        if path == "/api/v2/user_profile":
            return httpx.Response(404, json={"detail": "Not found."})
        if path == "/api/v2/users/me":
            return httpx.Response(404, json={"detail": "Not found."})
        if path == "/api/v2/users":
            return httpx.Response(200, json={"results": [{"id": 2, "username": "admin"}]})
        return httpx.Response(404, json={})

    me = _client(handler).myself()
    assert me["id"] == 2


def test_add_files_posts_multipart_title_and_file():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v2/findings/9/files/":
            seen["content_type"] = request.headers.get("content-type", "")
            seen["body"] = request.content
            return httpx.Response(201, json={"id": 3, "title": "shot.png", "file": "/media/shot.png"})
        return httpx.Response(404, json={})

    _client(handler).add_files("9", [("shot.png", b"png-bytes", "image/png")])
    assert "multipart" in seen["content_type"]
    assert b"shot.png" in seen["body"]
    assert b"png-bytes" in seen["body"]


def test_add_files_surfaces_dojo_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"file": ["No file was submitted."]})

    try:
        _client(handler).add_files("9", [("shot.png", b"x", "image/png")])
    except DefectDojoError as exc:
        assert "file" in str(exc).lower()
    else:
        raise AssertionError("expected DefectDojoError")
