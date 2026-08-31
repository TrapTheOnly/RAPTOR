from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx


_RETRYABLE_STATUSES = {301, 302, 303, 307, 308, 400, 404, 405, 410}


class JiraError(Exception):
    def __init__(
        self,
        message: str,
        status: int = 0,
        details: Optional[Any] = None,
        retryable: Optional[bool] = None,
    ):
        super().__init__(message)
        self.status = status
        self.details = details
        self.retryable = status in _RETRYABLE_STATUSES if retryable is None else bool(retryable)


def normalize_base_url(url: str) -> str:
    value = str(url or "").strip().rstrip("/")
    if not value:
        raise JiraError("Jira site URL is required.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise JiraError("Enter a full Jira URL, for example https://your-site.atlassian.net.")
    return value


class JiraClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        email: str = "",
        auth_type: str = "api_token",
        api_style: str = "auto",
        transport: Optional[httpx.Client] = None,
        timeout: float = 20.0,
    ):
        self.base_url = normalize_base_url(base_url)
        self.email = str(email or "").strip()
        self.token = str(token or "").strip()
        self.auth_type = str(auth_type or "api_token")
        self.api_style = str(api_style or "auto")
        self._owns_transport = transport is None
        headers = {"Accept": "application/json", "User-Agent": "RAPTOR-integrations"}
        auth = None
        if self.auth_type == "pat":
            headers["Authorization"] = f"Bearer {self.token}"
        else:
            if not self.email:
                raise JiraError("Jira email is required when using an API token.")
            auth = (self.email, self.token)
        self._client = transport or httpx.Client(
            base_url=self.base_url,
            headers=headers,
            auth=auth,
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_transport:
            self._client.close()

    def __enter__(self) -> "JiraClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise JiraError(f"Could not reach Jira: {exc}") from exc
        if 300 <= response.status_code < 400:
            raise JiraError("Jira redirected the request.", status=response.status_code)
        if response.status_code >= 400:
            message = _jira_error_message(response)
            raise JiraError(message, status=response.status_code, details=_safe_json(response))
        if response.status_code == 204 or not response.content:
            return None
        payload = _safe_json(response)
        if _is_non_json_payload(payload):
            # Server/DC has no API v3: httpx follows the 302 to login.jsp and gets HTML 200.
            raise JiraError(
                "Jira returned a non-JSON response.",
                status=response.status_code or 404,
                details=payload,
                retryable=True,
            )
        return payload

    def _api_prefixes(self) -> List[str]:
        if self.api_style == "3":
            return ["/rest/api/3"]
        if self.api_style == "2":
            return ["/rest/api/2"]
        return ["/rest/api/3", "/rest/api/2"]

    def _first_ok(self, method: str, suffix: str, **kwargs) -> Any:
        last_error: Optional[JiraError] = None
        for prefix in self._api_prefixes():
            try:
                result = self._request(method, f"{prefix}{suffix}", **kwargs)
                if self.api_style == "auto":
                    self.api_style = "3" if prefix.endswith("/3") else "2"
                return result
            except JiraError as exc:
                last_error = exc
                if not exc.retryable:
                    raise
        if last_error:
            raise last_error
        raise JiraError("Jira returned no response.")

    def myself(self) -> Dict[str, Any]:
        data = self._first_ok("GET", "/myself")
        if not isinstance(data, dict):
            raise JiraError("Jira did not return a user profile.")
        return data

    def list_projects(self) -> List[Dict[str, str]]:
        rows: Any = None
        last_error: Optional[JiraError] = None
        for suffix, params in (("/project", None), ("/project/search", {"maxResults": 100})):
            try:
                data = self._first_ok("GET", suffix, params=params) if params else self._first_ok("GET", suffix)
            except JiraError as exc:
                last_error = exc
                continue
            if isinstance(data, list):
                rows = data
                break
            if isinstance(data, dict) and isinstance(data.get("values"), list):
                rows = data["values"]
                break
        if rows is None:
            raise last_error or JiraError("Jira did not return any projects.")
        projects = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            projects.append(
                {
                    "id": str(row.get("id") or ""),
                    "key": str(row.get("key") or ""),
                    "name": str(row.get("name") or row.get("key") or ""),
                }
            )
        return projects

    def list_issue_types(self, project_key: str) -> List[Dict[str, str]]:
        key = str(project_key or "").strip()
        if not key:
            raise JiraError("Select a Jira project.")
        try:
            data = self._first_ok("GET", f"/issue/createmeta/{key}/issuetypes")
            rows = None
            if isinstance(data, dict):
                rows = data.get("issueTypes") or data.get("values") or data.get("issuetypes")
            elif isinstance(data, list):
                rows = data
        except JiraError:
            rows = None
        if not rows:
            try:
                data = self._first_ok(
                    "GET",
                    "/issue/createmeta",
                    params={"projectKeys": key, "expand": "projects.issuetypes"},
                )
                rows = _issue_types_from_createmeta(data)
            except JiraError as exc:
                if exc.status not in {404, 410}:
                    raise
                project = self._first_ok("GET", f"/project/{key}")
                rows = project.get("issueTypes") if isinstance(project, dict) else []
        types = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            types.append(
                {
                    "id": str(row.get("id") or ""),
                    "name": str(row.get("name") or ""),
                    "subtask": bool(row.get("subtask")),
                }
            )
        return [item for item in types if item["id"] and not item["subtask"]]

    def get_create_fields(self, project_key: str, issue_type_id: str) -> Dict[str, Any]:
        key = str(project_key or "").strip()
        type_id = str(issue_type_id or "").strip()
        if not key or not type_id:
            raise JiraError("Select a Jira project and issue type.")
        try:
            data = self._first_ok("GET", f"/issue/createmeta/{key}/issuetypes/{type_id}")
            fields = _fields_from_issuetype_meta(data)
            if fields:
                return fields
        except JiraError:
            pass
        try:
            data = self._first_ok(
                "GET",
                "/issue/createmeta",
                params={
                    "projectKeys": key,
                    "issuetypeIds": type_id,
                    "expand": "projects.issuetypes.fields",
                },
            )
            fields = _fields_from_createmeta(data)
            if fields:
                return fields
        except JiraError as exc:
            if exc.status not in {404, 410}:
                raise
        raise JiraError("Jira did not return fields for that issue type.")

    def create_issue(self, fields: Dict[str, Any]) -> Dict[str, str]:
        data = self._first_ok("POST", "/issue", json={"fields": fields})
        if not isinstance(data, dict) or not data.get("key"):
            raise JiraError("Jira created the issue but did not return a key.")
        key = str(data["key"])
        return {
            "id": str(data.get("id") or key),
            "key": key,
            "url": browse_url(self.base_url, key),
        }

    def add_attachments(self, issue_key: str, files: List[tuple]) -> None:
        key = str(issue_key or "").strip()
        if not key or not files:
            return
        for filename, content, content_type in files:
            self._first_ok(
                "POST",
                f"/issue/{key}/attachments",
                headers={"X-Atlassian-Token": "no-check"},
                files={"file": (str(filename), content, str(content_type or "application/octet-stream"))},
            )


def browse_url(base_url: str, key: str) -> str:
    return urljoin(str(base_url).rstrip("/") + "/", f"browse/{key}")


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:500]}


def _is_non_json_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and "raw" in payload and "errorMessages" not in payload and "errors" not in payload


def _jira_error_message(response: httpx.Response) -> str:
    payload = _safe_json(response)
    if isinstance(payload, dict):
        messages = payload.get("errorMessages") or []
        errors = payload.get("errors") or {}
        parts = [str(item) for item in messages if item]
        parts.extend(f"{key}: {value}" for key, value in errors.items())
        if parts:
            return "Jira: " + "; ".join(parts)
        if payload.get("message"):
            return f"Jira: {payload['message']}"
    return f"Jira returned HTTP {response.status_code}."


def _issue_types_from_createmeta(data: Any) -> List[Dict[str, Any]]:
    projects = data.get("projects") if isinstance(data, dict) else []
    if not projects:
        return []
    return list(projects[0].get("issuetypes") or [])


def _fields_from_issuetype_meta(data: Any) -> Dict[str, Any]:
    if isinstance(data, list):
        rows: Any = data
    elif isinstance(data, dict):
        rows = data.get("fields") if isinstance(data.get("fields"), (dict, list)) else data.get("values")
    else:
        rows = None
    if isinstance(rows, dict) and rows:
        return rows
    if not isinstance(rows, list):
        return {}
    parsed: Dict[str, Any] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        field_id = str(item.get("fieldId") or item.get("key") or "")
        if field_id:
            parsed[field_id] = item
    return parsed


def _fields_from_createmeta(data: Any) -> Dict[str, Any]:
    types = _issue_types_from_createmeta(data)
    if not types:
        return {}
    fields = types[0].get("fields") or {}
    return fields if isinstance(fields, dict) else {}
