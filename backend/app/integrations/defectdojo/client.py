from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx


class DefectDojoError(Exception):
    def __init__(self, message: str, status: int = 0, details: Optional[Any] = None):
        super().__init__(message)
        self.status = status
        self.details = details


def normalize_base_url(url: str) -> str:
    value = str(url or "").strip().rstrip("/")
    if value.endswith("/api/v2"):
        value = value[: -len("/api/v2")]
    if not value:
        raise DefectDojoError("DefectDojo URL is required.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DefectDojoError("Enter a full DefectDojo URL, for example https://dojo.example.com.")
    return value


class DefectDojoClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        transport: Optional[httpx.Client] = None,
        timeout: float = 20.0,
    ):
        self.base_url = normalize_base_url(base_url)
        self.token = str(token or "").strip()
        if not self.token:
            raise DefectDojoError("DefectDojo API key is required.")
        self._owns_transport = transport is None
        self._client = transport or httpx.Client(
            base_url=self.base_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Token {self.token}",
                "User-Agent": "RAPTOR-integrations",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_transport:
            self._client.close()

    def __enter__(self) -> "DefectDojoClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DefectDojoError(f"Could not reach DefectDojo: {exc}") from exc
        if response.status_code >= 400:
            raise DefectDojoError(_dojo_error_message(response), status=response.status_code, details=_safe_json(response))
        if response.status_code == 204 or not response.content:
            return None
        return _safe_json(response)

    def _try_request(self, method: str, path: str, **kwargs) -> Any:
        try:
            return self._request(method, path, **kwargs)
        except DefectDojoError as exc:
            if exc.status in {404, 405}:
                return None
            raise

    def _list(self, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        data = self._request("GET", path, params=params or {})
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            rows = data.get("results") or data.get("objects") or []
            return [item for item in rows if isinstance(item, dict)]
        return []

    def myself(self) -> Dict[str, Any]:
        profile = self._try_request("GET", "/api/v2/user_profile/")
        user = _user_from_payload(profile)
        if user:
            return user
        me = self._try_request("GET", "/api/v2/users/me/")
        user = _user_from_payload(me)
        if user:
            return user
        users = self._list("/api/v2/users/", {"limit": 1})
        if users:
            return users[0]
        raise DefectDojoError("DefectDojo accepted the key but did not return a user.")

    def list_products(self) -> List[Dict[str, str]]:
        rows = self._list("/api/v2/products/", {"limit": 200})
        return [
            {
                "id": str(row.get("id") or ""),
                "name": str(row.get("name") or row.get("id") or ""),
            }
            for row in rows
            if row.get("id") is not None
        ]

    def list_engagements(self, product_id: str) -> List[Dict[str, str]]:
        rows = self._list("/api/v2/engagements/", {"product": product_id, "limit": 200})
        return [
            {
                "id": str(row.get("id") or ""),
                "name": str(row.get("name") or row.get("id") or ""),
                "product": str(row.get("product") or product_id),
            }
            for row in rows
            if row.get("id") is not None
        ]

    def list_tests(self, engagement_id: str) -> List[Dict[str, str]]:
        rows = self._list("/api/v2/tests/", {"engagement": engagement_id, "limit": 200})
        return [
            {
                "id": str(row.get("id") or ""),
                "name": str(row.get("title") or row.get("name") or row.get("id") or ""),
                "engagement": str(row.get("engagement") or engagement_id),
            }
            for row in rows
            if row.get("id") is not None
        ]

    def find_or_create_engagement(self, product_id: str, name: str) -> Dict[str, str]:
        existing = self.list_engagements(product_id)
        for row in existing:
            if row["name"].lower() == str(name).strip().lower():
                return row
        today = date.today().isoformat()
        created = self._request(
            "POST",
            "/api/v2/engagements/",
            json={
                "name": str(name).strip()[:255],
                "product": int(product_id),
                "target_start": today,
                "target_end": today,
                "engagement_type": "Interactive",
                "status": "In Progress",
            },
        )
        if not isinstance(created, dict) or created.get("id") is None:
            raise DefectDojoError("DefectDojo did not create the engagement.")
        return {"id": str(created["id"]), "name": str(created.get("name") or name), "product": str(product_id)}

    def _default_test_type_id(self) -> int:
        rows = self._list("/api/v2/test_types/", {"limit": 200})
        preferred = None
        for row in rows:
            name = str(row.get("name") or "").lower()
            if name == "manual code review" or name == "raptor":
                return int(row["id"])
            if preferred is None and "manual" in name:
                preferred = int(row["id"])
        if preferred is not None:
            return preferred
        if rows:
            return int(rows[0]["id"])
        raise DefectDojoError("DefectDojo has no test types available.")

    def find_or_create_test(self, engagement_id: str, title: str = "RAPTOR") -> Dict[str, str]:
        existing = self.list_tests(engagement_id)
        for row in existing:
            if row["name"].lower() == str(title).strip().lower():
                return row
        today = date.today().isoformat()
        created = self._request(
            "POST",
            "/api/v2/tests/",
            json={
                "engagement": int(engagement_id),
                "title": str(title).strip()[:255],
                "target_start": today,
                "target_end": today,
                "test_type": self._default_test_type_id(),
            },
        )
        if not isinstance(created, dict) or created.get("id") is None:
            raise DefectDojoError("DefectDojo did not create the test.")
        return {
            "id": str(created["id"]),
            "name": str(created.get("title") or title),
            "engagement": str(engagement_id),
        }

    def create_finding(self, payload: Dict[str, Any]) -> Dict[str, str]:
        created = self._request("POST", "/api/v2/findings/", json=payload)
        if not isinstance(created, dict) or created.get("id") is None:
            raise DefectDojoError("DefectDojo did not create the finding.")
        finding_id = str(created["id"])
        return {
            "id": finding_id,
            "url": f"{self.base_url}/finding/{finding_id}",
        }

    def add_files(self, finding_id: str, files: List[tuple]) -> None:
        target = str(finding_id or "").strip()
        if not target or not files:
            return
        for filename, content, content_type in files:
            title = str(filename or "evidence")[:100]
            self._request(
                "POST",
                f"/api/v2/findings/{target}/files/",
                data={"title": title},
                files={"file": (str(filename or title), content, str(content_type or "application/octet-stream"))},
            )


def _user_from_payload(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
    if isinstance(user, dict) and user.get("id") is not None:
        return user
    return None


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:500]}


def _dojo_error_message(response: httpx.Response) -> str:
    payload = _safe_json(response)
    if isinstance(payload, dict):
        if payload.get("detail"):
            return f"DefectDojo: {payload['detail']}"
        if payload.get("message"):
            return f"DefectDojo: {payload['message']}"
        parts = []
        for key, value in payload.items():
            if key in {"detail", "message"}:
                continue
            parts.append(f"{key}: {value}")
        if parts:
            return "DefectDojo: " + "; ".join(parts)
    return f"DefectDojo returned HTTP {response.status_code}."
