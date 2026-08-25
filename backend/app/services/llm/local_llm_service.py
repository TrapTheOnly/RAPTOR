"""Proxy the local-llm sidecar for install/status/progress."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterator, Tuple

import httpx

logger = logging.getLogger(__name__)

LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://local-llm:8083")
SCANNER_INTERNAL_TOKEN = os.getenv("SCANNER_INTERNAL_TOKEN", "")
UNREACHABLE = {
    "state": "unavailable",
    "error": "Local model runtime is not running. Start the scanner stack.",
    "bytes_done": 0,
    "bytes_total": 0,
    "ready": False,
}


def _headers() -> Dict[str, str]:
    return {"X-Scanner-Token": SCANNER_INTERNAL_TOKEN}


def fetch_local_status() -> Dict[str, Any]:
    url = f"{LOCAL_LLM_BASE_URL.rstrip('/')}/status"
    try:
        with httpx.Client(timeout=5.0, trust_env=False) as client:
            response = client.get(url, headers=_headers())
        if response.status_code >= 400:
            payload = dict(UNREACHABLE)
            payload["error"] = f"Local runtime returned {response.status_code}."
            return payload
        data = response.json()
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.debug("local-llm status failed: %s", exc)
    return dict(UNREACHABLE)


def get_local_status_service() -> Tuple[Dict[str, Any], int]:
    from app.repositories.llm_connections_repository import ensure_local_connection, get_local_connection
    from app.services.llm.connections_service import maybe_autoselect_local

    ensure_local_connection()
    status = fetch_local_status()
    if str(status.get("state") or "") == "ready":
        maybe_autoselect_local()
    connection = get_local_connection(mask=True)
    return {"status": status, "connection": connection}, 200


def _post_action(path: str) -> Tuple[Dict[str, Any], int]:
    url = f"{LOCAL_LLM_BASE_URL.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=30.0, trust_env=False) as client:
            response = client.post(url, headers=_headers())
    except Exception as exc:
        logger.warning("local-llm %s failed: %s", path, exc)
        return {"error": "Local model runtime is not running. Start the scanner stack."}, 503
    try:
        payload = response.json()
    except ValueError:
        payload = {"error": response.text[:240] or "Local runtime error."}
    if not isinstance(payload, dict):
        payload = {"error": "Unexpected local runtime response."}
    return payload, response.status_code


def install_local_service() -> Tuple[Dict[str, Any], int]:
    return _post_action("/install")


def cancel_local_service() -> Tuple[Dict[str, Any], int]:
    return _post_action("/cancel")


def pause_local_service() -> Tuple[Dict[str, Any], int]:
    return _post_action("/pause")


def resume_local_service() -> Tuple[Dict[str, Any], int]:
    return _post_action("/resume")


def start_local_service() -> Tuple[Dict[str, Any], int]:
    payload, status = _post_action("/start")
    if status < 400:
        from app.services.llm.connections_service import maybe_autoselect_local

        maybe_autoselect_local()
    return payload, status


def stop_local_service() -> Tuple[Dict[str, Any], int]:
    return _post_action("/stop")


def uninstall_local_service() -> Tuple[Dict[str, Any], int]:
    return _post_action("/uninstall")


def iter_local_events() -> Iterator[str]:
    url = f"{LOCAL_LLM_BASE_URL.rstrip('/')}/events"
    try:
        with httpx.Client(timeout=None, trust_env=False) as client:
            with client.stream("GET", url, headers=_headers()) as response:
                if response.status_code >= 400:
                    yield f"data: {json.dumps(UNREACHABLE)}\n\n"
                    return
                for line in response.iter_lines():
                    if line is None:
                        continue
                    text = line.decode("utf-8") if isinstance(line, bytes) else str(line)
                    yield text + "\n"
    except Exception as exc:
        logger.debug("local-llm events failed: %s", exc)
        yield 'data: {"state":"unavailable"}\n\n'


__all__ = [
    "cancel_local_service",
    "fetch_local_status",
    "get_local_status_service",
    "install_local_service",
    "iter_local_events",
    "pause_local_service",
    "resume_local_service",
    "start_local_service",
    "stop_local_service",
    "uninstall_local_service",
]
