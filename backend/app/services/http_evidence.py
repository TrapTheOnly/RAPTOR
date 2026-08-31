"""HTTP request/response markdown for finding evidence (Burp-style split)."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

SEPARATOR = "==="


def _header_lines(headers: Optional[Mapping[str, Any]]) -> list[str]:
    lines: list[str] = []
    for key, value in dict(headers or {}).items():
        name = str(key or "").strip()
        if not name:
            continue
        if isinstance(value, (list, tuple)):
            text = ", ".join(str(item) for item in value if str(item).strip())
        else:
            text = str(value or "")
        lines.append(f"{name}: {text}")
    return lines


def _request_block(
    *,
    method: str,
    path: str,
    host: str,
    query: str = "",
    headers: Optional[Mapping[str, Any]] = None,
    body: str = "",
) -> str:
    verb = (method or "GET").strip().upper() or "GET"
    target = path or "/"
    if not target.startswith("/"):
        target = "/" + target
    q = str(query or "").lstrip("?")
    if q:
        target = f"{target}?{q}"
    lines = [f"{verb} {target} HTTP/1.1"]
    host_name = str(host or "").strip()
    header_map = dict(headers or {})
    has_host = any(str(key).lower() == "host" for key in header_map)
    if host_name and not has_host:
        lines.append(f"Host: {host_name}")
    lines.extend(_header_lines(header_map))
    blob = str(body or "").strip("\n")
    if blob:
        lines.extend(["", blob])
    return "\n".join(lines).rstrip()


def _response_block(
    *,
    status: Any = None,
    reason: str = "",
    headers: Optional[Mapping[str, Any]] = None,
    body: str = "",
) -> str:
    try:
        code = int(status) if status not in (None, "") else None
    except (TypeError, ValueError):
        code = None
    if code is None and not str(body or "").strip() and not headers:
        return ""
    reason_text = str(reason or "").strip()
    status_line = f"HTTP/1.1 {code if code is not None else ''}".rstrip()
    if reason_text:
        status_line = f"{status_line} {reason_text}".strip()
    lines = [status_line or "HTTP/1.1"]
    lines.extend(_header_lines(headers))
    blob = str(body or "").strip("\n")
    if blob:
        lines.extend(["", blob])
    return "\n".join(lines).rstrip()


def format_http_exchange(
    *,
    method: str = "GET",
    path: str = "/",
    host: str = "",
    query: str = "",
    headers: Optional[Mapping[str, Any]] = None,
    body: str = "",
    status: Any = None,
    reason: str = "",
    response_headers: Optional[Mapping[str, Any]] = None,
    response_body: str = "",
) -> str:
    """One ```http fence. Request, then ===, then response when a status exists."""
    request = _request_block(
        method=method, path=path, host=host, query=query, headers=headers, body=body
    )
    response = _response_block(
        status=status, reason=reason, headers=response_headers, body=response_body
    )
    if not request.strip():
        return ""
    if not response.strip():
        return f"```http\n{request}\n```\n"
    return f"```http\n{request}\n\n{SEPARATOR}\n\n{response}\n```\n"


def markdown_from_event(event: Optional[Dict[str, Any]]) -> str:
    if not isinstance(event, dict):
        return ""
    excerpt = event.get("excerpt_json") if isinstance(event.get("excerpt_json"), dict) else {}
    return format_http_exchange(
        method=str(event.get("method") or "GET"),
        path=str(event.get("path") or "/"),
        host=str(event.get("host") or ""),
        query=str(excerpt.get("query") or ""),
        headers=excerpt.get("headers") if isinstance(excerpt.get("headers"), dict) else {},
        body=str(excerpt.get("body") or ""),
        status=event.get("status"),
        response_body=str(excerpt.get("response_body") or ""),
        response_headers=excerpt.get("response_headers")
        if isinstance(excerpt.get("response_headers"), dict)
        else None,
    )
