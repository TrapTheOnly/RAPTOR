import logging
from json import JSONDecodeError
from typing import Any, Dict, Optional

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


LIST_PAGE_SIZE = 500
LIST_PAGE_CAP = 100


async def fetch_service_dataset(
    path: str,
    settings: MCPSettings,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{settings.raptor_api_base_url}{path}"
    timeout = httpx.Timeout(settings.raptor_api_timeout_seconds)
    headers = {"X-API-Key": settings.raptor_service_api_key}
    request_kwargs: Dict[str, Any] = {"headers": headers}
    if params:
        request_kwargs["params"] = params

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, **request_kwargs)
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


async def fetch_all_service_pages(
    path: str,
    collection_key: str,
    settings: MCPSettings,
) -> Any:
    offset = 0
    items: list[Any] = []
    last_payload: Dict[str, Any] = {}
    for _ in range(LIST_PAGE_CAP):
        payload = await fetch_service_dataset(
            path,
            settings,
            params={"limit": LIST_PAGE_SIZE, "offset": offset},
        )
        if not isinstance(payload, dict):
            return payload
        last_payload = payload
        page = payload.get(collection_key)
        if not isinstance(page, list):
            return payload
        items.extend(page)
        if len(page) < LIST_PAGE_SIZE:
            break
        offset += LIST_PAGE_SIZE
    result = dict(last_payload)
    result[collection_key] = items
    result["count"] = len(items)
    result["limit"] = len(items)
    result["offset"] = 0
    return result


__all__ = ["_sanitize_upstream_error", "fetch_all_service_pages", "fetch_service_dataset"]
