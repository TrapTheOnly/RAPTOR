import asyncio
import logging
from json import JSONDecodeError
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from raptor_mcp.settings import MCPSettings, load_settings

logger = logging.getLogger(__name__)

mcp = FastMCP(name="raptor-mcp", streamable_http_path="/mcp")


def _sanitize_upstream_error(response: httpx.Response) -> str:
    default_message = "Upstream request failed"
    try:
        payload = response.json()
    except JSONDecodeError:
        return default_message

    if isinstance(payload, dict):
        raw_error = payload.get("error")
        if isinstance(raw_error, str):
            cleaned = raw_error.strip().replace("\n", " ")
            if cleaned:
                return cleaned[:200]
    return default_message


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
        payload = response.json()
    except JSONDecodeError as exc:
        raise RuntimeError("RAPTOR API returned a non-JSON response.") from exc

    return payload


@mcp.tool(name="list_records", description="Fetch full records dataset from RAPTOR service API")
async def list_records() -> Any:
    settings = load_settings()
    return await fetch_service_dataset("/service-api/v1/records", settings)


@mcp.tool(name="list_pentests", description="Fetch full pentests dataset from RAPTOR service API")
async def list_pentests() -> Any:
    settings = load_settings()
    return await fetch_service_dataset("/service-api/v1/pentests", settings)


def run_records_tool_sync(settings: MCPSettings) -> Any:
    return asyncio.run(fetch_service_dataset("/service-api/v1/records", settings))


def run_pentests_tool_sync(settings: MCPSettings) -> Any:
    return asyncio.run(fetch_service_dataset("/service-api/v1/pentests", settings))


__all__ = [
    "fetch_service_dataset",
    "list_pentests",
    "list_records",
    "mcp",
    "run_pentests_tool_sync",
    "run_records_tool_sync",
]
