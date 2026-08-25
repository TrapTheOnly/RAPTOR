"""Anthropic Messages adapter (direct, Bedrock, custom compatible)."""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic
import httpx

from scanner.llm.types import ToolCall, Turn, Usage
from scanner.settings import ScanSettings

logger = logging.getLogger(__name__)


def _proxy_client(settings: ScanSettings):
    proxy_url = settings.proxy_url.strip()
    if not proxy_url:
        return None
    return httpx.Client(
        proxy=proxy_url,
        mounts={"http://mcp": None, "http://app": None, "http://kali": None, "http://local-llm": None},
    )


def _block_to_dict(block: Any) -> dict:
    if isinstance(block, dict):
        return dict(block)
    payload = {"type": getattr(block, "type", "text")}
    if payload["type"] == "text":
        payload["text"] = getattr(block, "text", "") or ""
    elif payload["type"] == "tool_use":
        payload["id"] = getattr(block, "id", "")
        payload["name"] = getattr(block, "name", "")
        payload["input"] = getattr(block, "input", {}) or {}
    elif payload["type"] == "thinking":
        payload["thinking"] = getattr(block, "thinking", "") or ""
    return payload


class AnthropicMessagesClient:
    protocol = "anthropic"

    def __init__(self, settings: ScanSettings):
        self.settings = settings
        self.display_name = settings.provider_display_name or settings.provider_type
        self.model_id = settings.model_id
        http_client = _proxy_client(settings)
        kwargs: dict[str, Any] = {}
        if http_client is not None:
            kwargs["http_client"] = http_client
        if settings.provider_type == "bedrock":
            bearer = settings.aws_bearer_token or settings.api_key or os.getenv("AWS_BEARER_TOKEN_BEDROCK") or ""
            if bearer:
                kwargs["api_key"] = bearer
            else:
                if settings.aws_access_key:
                    kwargs["aws_access_key"] = settings.aws_access_key
                if settings.aws_secret_key:
                    kwargs["aws_secret_key"] = settings.aws_secret_key
                if settings.aws_session_token:
                    kwargs["aws_session_token"] = settings.aws_session_token
            self._client = anthropic.AnthropicBedrock(
                aws_region=settings.aws_region or "us-east-1",
                **kwargs,
            )
            return
        if settings.api_key:
            kwargs["api_key"] = settings.api_key
        if settings.base_url:
            kwargs["base_url"] = settings.base_url
        self._client = anthropic.Anthropic(**kwargs)

    def complete(
        self,
        *,
        system: list[dict],
        tools: list[dict],
        messages: list[dict],
        max_tokens: int,
        thinking_budget_tokens: int,
    ) -> Turn:
        create_kwargs: dict[str, Any] = dict(
            model=self.model_id,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        if thinking_budget_tokens > 0:
            create_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget_tokens,
            }
        response = self._client.messages.create(**create_kwargs)
        content = [_block_to_dict(block) for block in response.content]
        tool_calls = [
            ToolCall(id=str(block.get("id") or ""), name=str(block.get("name") or ""), input=block.get("input") or {})
            for block in content
            if block.get("type") == "tool_use"
        ]
        usage = getattr(response, "usage", None)
        return Turn(
            stop_reason=str(getattr(response, "stop_reason", "") or ""),
            content=content,
            tool_calls=tool_calls,
            usage=Usage(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                cache_read_input_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
                cache_creation_input_tokens=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
            ),
        )

    def count_tokens(
        self,
        *,
        system: list[dict],
        tools: list[dict],
        messages: list[dict],
    ) -> int | None:
        try:
            response = self._client.messages.count_tokens(
                model=self.model_id,
                system=system,
                tools=tools,
                messages=messages,
            )
        except Exception as exc:
            logger.debug("Token preflight failed: %s", exc)
            return None
        return int(getattr(response, "input_tokens", 0) or 0)
