import logging
from json import JSONDecodeError
from typing import Any

import httpx

from raptor_mcp.settings import MCPSettings

logger = logging.getLogger(__name__)


def _sanitize_upstream_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except JSONDecodeError:
        return "Upstream request failed"
    if isinstance(payload, dict):
        raw = payload.get("error")
        if isinstance(raw, str):
            cleaned = raw.strip().replace("\n", " ")
            if cleaned:
                return cleaned[:200]
    return "Upstream request failed"


async def fetch_service_dataset(path: str, settings: MCPSettings) -> Any:
    url = f"{settings.raptor_api_base_url}{path}"
    timeout = httpx.Timeout(settings.raptor_api_timeout_seconds)
    headers = {"X-API-Key": settings.raptor_service_api_key}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise RuntimeError("RAPTOR API request timed out. Retry later.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Failed to connect to RAPTOR API. Retry later.") from exc

    if response.status_code >= 400:
        error_text = _sanitize_upstream_error(response)
        raise RuntimeError(f"RAPTOR API error ({response.status_code}): {error_text}")

    try:
        return response.json()
    except JSONDecodeError as exc:
        raise RuntimeError("RAPTOR API returned a non-JSON response.") from exc


__all__ = ["_sanitize_upstream_error", "fetch_service_dataset"]
