"""Thin async wrapper around the RAPTOR MCP session."""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def raptor_mcp_session(base_url: str, token: str) -> AsyncIterator[ClientSession]:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url.rstrip('/')}/mcp"
    async with streamablehttp_client(url, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            yield session


async def call_tool(session: ClientSession, tool_name: str, arguments: dict) -> Any:
    result = await session.call_tool(tool_name, arguments)
    if result.isError:
        raise RuntimeError(f"MCP tool {tool_name!r} returned error: {result.content}")
    if result.content and hasattr(result.content[0], "text"):
        raw = result.content[0].text
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    return None


__all__ = ["call_tool", "raptor_mcp_session"]
