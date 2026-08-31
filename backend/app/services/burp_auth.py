import logging
import re
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

from app.domain.burp.fields import normalize_host, parse_notes_credentials
from app.integrations.secrets import decrypt_secret
from app.repositories import burp_repository, phase2b_repository
from app.repositories.offsec.offsec_records import get_pentest_row

logger = logging.getLogger(__name__)

EMPTY_NOTES_ERROR = "add credentials to security details."
AUTH_FAILED_ERROR = "Authentication retry failed. Check the stored template and security details."


def notes_for_host(wave: Dict[str, Any], host: str) -> str:
    target = normalize_host(host)
    hosts = phase2b_repository.list_live_wave_hosts(wave)
    matched = None
    fallback = None
    for row in hosts:
        name = normalize_host(str(row.get("name") or ""))
        if not fallback and row.get("in_scope") is not False:
            fallback = row
        if target and (name == target or name.endswith("." + target) or target.endswith("." + name)):
            matched = row
            break
    record = matched or fallback
    if not record:
        return ""
    pentest = get_pentest_row(int(record["id"])) or {}
    return str(pentest.get("notes") or "")


def credentials_from_notes(wave: Dict[str, Any], host: str) -> Tuple[Dict[str, str], Optional[str]]:
    notes = notes_for_host(wave, host)
    creds = parse_notes_credentials(notes)
    if not creds.get("username") and not creds.get("password") and not creds.get("token"):
        return {}, EMPTY_NOTES_ERROR
    return creds, None


def _substitute(text: str, creds: Dict[str, str]) -> str:
    out = str(text or "")
    for key, value in creds.items():
        out = out.replace("{{" + key + "}}", value)
        out = out.replace("{{" + key.upper() + "}}", value)
    return out


def _parse_raw_request(raw: str) -> Dict[str, Any]:
    text = raw.replace("\r\n", "\n")
    if "\n\n" in text:
        head, body = text.split("\n\n", 1)
    else:
        head, body = text, ""
    lines = head.split("\n")
    start = lines[0] if lines else "POST / HTTP/1.1"
    parts = start.split()
    method = parts[0] if parts else "POST"
    path = parts[1] if len(parts) > 1 else "/"
    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip()] = value.strip()
    return {"method": method, "path": path, "headers": headers, "body": body}


def extract_token(response: httpx.Response, rule: Dict[str, Any]) -> str:
    kind = str(rule.get("type") or rule.get("kind") or "header").strip().lower()
    name = str(rule.get("name") or rule.get("path") or "Authorization").strip()
    if kind in {"header", "authorization"}:
        value = response.headers.get(name) or response.headers.get("Authorization") or ""
        if value.lower().startswith("bearer "):
            return value[7:].strip()
        return value.strip()
    if kind in {"cookie", "set-cookie"}:
        cookie_name = name or "session"
        return str(response.cookies.get(cookie_name) or "").strip()
    if kind in {"body_json", "json", "json_path"}:
        try:
            payload = response.json()
        except Exception:
            return ""
        path = name.strip(".")
        current: Any = payload
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return ""
        return str(current or "").strip()
    match = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", response.text or "")
    return match.group(0) if match else ""


def apply_extracted_token(headers: Dict[str, str], token: str, rule: Dict[str, Any]) -> Dict[str, str]:
    out = dict(headers)
    kind = str(rule.get("apply_type") or rule.get("type") or "header").strip().lower()
    name = str(rule.get("apply_name") or rule.get("name") or "Authorization").strip()
    if not token:
        return out
    if kind in {"cookie", "set-cookie"}:
        cookie = out.get("Cookie") or out.get("cookie") or ""
        cookie_name = name or "session"
        assignment = f"{cookie_name}={token}"
        out["Cookie"] = f"{cookie}; {assignment}" if cookie else assignment
        return out
    if kind == "header" and name.lower() != "authorization":
        out[name] = token
        return out
    out["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    return out


def login_with_template(
    template: Dict[str, Any],
    creds: Dict[str, str],
    timeout: float = 15.0,
) -> Tuple[Optional[str], Optional[str]]:
    try:
        raw = decrypt_secret(template.get("request_ciphertext"))
    except ValueError as exc:
        return None, str(exc)
    parsed = _parse_raw_request(_substitute(raw, creds))
    host = str(template.get("host") or parsed["headers"].get("Host") or "")
    scheme = "https"
    url = f"{scheme}://{host}{parsed['path']}"
    headers = {k: v for k, v in parsed["headers"].items() if k.lower() != "content-length"}
    try:
        response = httpx.request(
            parsed["method"],
            url,
            headers=headers,
            content=_substitute(parsed["body"], creds).encode("utf-8"),
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        logger.warning("Burp auth template login failed: %s", exc)
        return None, str(exc)
    token = extract_token(response, template.get("extract_rule") or {})
    if not token:
        return None, "Login succeeded but no token matched the extract rule."
    return token, None


def request_with_auth_retry(
    wave: Dict[str, Any],
    *,
    host: str,
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    body: bytes | str | None = None,
    timeout: float = 15.0,
    transport: Optional[Callable[..., httpx.Response]] = None,
) -> Tuple[httpx.Response, Dict[str, Any]]:
    """Send one HTTP request. On 401/403, fill the auth template once and retry once."""
    do_request = transport or httpx.request
    request_headers = dict(headers or {})
    content = body.encode("utf-8") if isinstance(body, str) else body
    first = do_request(method, url, headers=request_headers, content=content, timeout=timeout, follow_redirects=True)
    meta: Dict[str, Any] = {"retried": False}
    if first.status_code not in {401, 403}:
        return first, meta

    template = burp_repository.get_auth_template(int(wave["id"]), normalize_host(host))
    if not template:
        template = burp_repository.get_auth_template(int(wave["id"]))
    if not template:
        meta["auth_error"] = "No authentication request is stored for this wave."
        return first, meta
    creds, creds_error = credentials_from_notes(wave, host or template.get("host") or "")
    if creds_error:
        meta["auth_error"] = creds_error
        return first, meta
    token, login_error = login_with_template(template, creds, timeout=timeout)
    if login_error or not token:
        meta["auth_error"] = login_error or AUTH_FAILED_ERROR
        return first, meta
    retry_headers = apply_extracted_token(request_headers, token, template.get("extract_rule") or {})
    second = do_request(method, url, headers=retry_headers, content=content, timeout=timeout, follow_redirects=True)
    meta["retried"] = True
    return second, meta
