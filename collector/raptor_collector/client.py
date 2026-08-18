"""HTTP client for RAPTOR collector enroll, heartbeat, and ingest."""

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class CollectorClientError(RuntimeError):
    def __init__(self, message: str, status_code: int = 0, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class CollectorClient:
    def __init__(self, base_url: str, token: str = "", timeout: int = 30, cafile: str = "") -> None:
        self.base_url = str(base_url or "").rstrip("/") + "/"
        self.token = str(token or "").strip()
        self.timeout = timeout
        self.cafile = cafile or os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or ""

    def _context(self) -> Optional[ssl.SSLContext]:
        if self.cafile:
            return ssl.create_default_context(cafile=self.cafile)
        return ssl.create_default_context()

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None, token: Optional[str] = None) -> Dict[str, Any]:
        url = urljoin(self.base_url, path.lstrip("/"))
        data = json.dumps(body or {}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        bearer = token if token is not None else self.token
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
            headers["X-Collector-Token"] = bearer
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self._context()) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"error": raw}
            raise CollectorClientError(
                str(payload.get("error") or exc.reason or "HTTP error"),
                status_code=exc.code,
                payload=payload,
            ) from exc
        except urllib.error.URLError as exc:
            raise CollectorClientError(f"Failed to reach RAPTOR: {exc.reason}") from exc

    def enroll(self, enroll_token: str, hostname: str, agent_version: str) -> Dict[str, Any]:
        payload = self._request(
            "POST",
            "/collector/v1/enroll",
            {"token": enroll_token, "hostname": hostname, "agent_version": agent_version},
            token="",
        )
        if payload.get("token"):
            self.token = str(payload["token"])
        return payload

    def heartbeat(self, zones: list, agent_version: str, soa_serial: str = "") -> Dict[str, Any]:
        payload = self._request(
            "POST",
            "/collector/v1/heartbeat",
            {"zones": zones, "agent_version": agent_version, "soa_serial": soa_serial},
        )
        if payload.get("token"):
            self.token = str(payload["token"])
        return payload

    def ingest(self, source_id: int, zones: list, agent_version: str, cursor: str = "") -> Dict[str, Any]:
        payload = self._request(
            "POST",
            "/collector/v1/ingest",
            {
                "source_id": source_id,
                "zones": zones,
                "agent_version": agent_version,
                "cursor": cursor,
            },
        )
        if payload.get("token"):
            self.token = str(payload["token"])
        return payload
