"""OpenAI Chat Completions adapter (OpenAI, Gemini, Azure, Oracle, local, custom)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from scanner.llm.types import ToolCall, Turn, Usage
from scanner.settings import ScanSettings

logger = logging.getLogger(__name__)


def _openai_tools(tools: list[dict]) -> list[dict]:
    converted = []
    for tool in tools:
        name = str(tool.get("name") or "")
        if not name:
            continue
        parameters = tool.get("input_schema") or tool.get("parameters") or {"type": "object", "properties": {}}
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": str(tool.get("description") or ""),
                    "parameters": parameters,
                },
            }
        )
    return converted


def _flatten_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
        elif isinstance(block, dict) and block.get("text"):
            parts.append(str(block.get("text") or ""))
    return "\n".join(part for part in parts if part)


def _to_openai_messages(system: list[dict], messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    system_text = _flatten_text(system)
    if system_text:
        out.append({"role": "system", "content": system_text})
    for message in messages:
        role = str(message.get("role") or "user")
        content = message.get("content")
        if role == "assistant":
            text = _flatten_text(content)
            tool_calls = []
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    tool_calls.append(
                        {
                            "id": str(block.get("id") or ""),
                            "type": "function",
                            "function": {
                                "name": str(block.get("name") or ""),
                                "arguments": json.dumps(block.get("input") or {}),
                            },
                        }
                    )
            payload: dict[str, Any] = {"role": "assistant", "content": text or None}
            if tool_calls:
                payload["tool_calls"] = tool_calls
            out.append(payload)
            continue
        if isinstance(content, list) and any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content):
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(block.get("tool_use_id") or ""),
                        "content": str(block.get("content") or ""),
                    }
                )
            continue
        out.append({"role": role, "content": _flatten_text(content)})
    return out


class OpenAIChatClient:
    protocol = "openai"

    def __init__(self, settings: ScanSettings):
        self.settings = settings
        self.display_name = settings.provider_display_name or settings.provider_type
        self.model_id = settings.model_id
        self._timeout = 120.0

    def _url(self) -> str:
        if self.settings.provider_type == "azure":
            endpoint = (self.settings.base_url or "").rstrip("/")
            version = self.settings.azure_api_version or "2024-10-21"
            return f"{endpoint}/openai/deployments/{self.model_id}/chat/completions?api-version={version}"
        base = (self.settings.base_url or "").rstrip("/")
        return f"{base}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        for key, value in (self.settings.extra_headers or {}).items():
            if key and value not in (None, ""):
                headers[str(key)] = str(value)
        if self.settings.provider_type == "azure":
            if self.settings.api_key:
                headers["api-key"] = self.settings.api_key
        elif self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        if self.settings.project_ocid:
            headers["OpenAI-Project"] = self.settings.project_ocid
        return headers

    def complete(
        self,
        *,
        system: list[dict],
        tools: list[dict],
        messages: list[dict],
        max_tokens: int,
        thinking_budget_tokens: int,
    ) -> Turn:
        del thinking_budget_tokens
        payload: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": _to_openai_messages(system, messages),
        }
        openai_tools = _openai_tools(tools)
        if openai_tools:
            payload["tools"] = openai_tools
            payload["tool_choice"] = "auto"
        proxy = None if self.settings.provider_type == "local" else (self.settings.proxy_url.strip() or None)
        mounts = None
        if proxy:
            mounts = {
                "http://mcp": None,
                "http://app": None,
                "http://kali": None,
                "http://local-llm": None,
                "http://127.0.0.1": None,
                "http://localhost": None,
            }
        with httpx.Client(timeout=self._timeout, proxy=proxy, mounts=mounts) as client:
            response = client.post(self._url(), headers=self._headers(), json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"LLM request failed ({response.status_code}): {response.text[:300]}")
        data = response.json()
        choice = ((data.get("choices") or [{}])[0]) if isinstance(data, dict) else {}
        message = choice.get("message") or {}
        content_blocks: list[dict] = []
        text = message.get("content")
        if isinstance(text, str) and text:
            content_blocks.append({"type": "text", "text": text})
        tool_calls: list[ToolCall] = []
        for item in message.get("tool_calls") or []:
            function = item.get("function") or {}
            raw_args = function.get("arguments") or "{}"
            try:
                parsed = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
            except json.JSONDecodeError:
                parsed = {"raw": raw_args}
            call = ToolCall(
                id=str(item.get("id") or ""),
                name=str(function.get("name") or ""),
                input=parsed if isinstance(parsed, dict) else {"value": parsed},
            )
            tool_calls.append(call)
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.input,
                }
            )
        usage = data.get("usage") or {}
        finish = str(choice.get("finish_reason") or "")
        if tool_calls:
            stop_reason = "tool_use"
        elif finish in {"stop", "end_turn"}:
            stop_reason = "end_turn"
        else:
            stop_reason = finish or "end_turn"
        return Turn(
            stop_reason=stop_reason,
            content=content_blocks,
            tool_calls=tool_calls,
            usage=Usage(
                input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            ),
        )

    def count_tokens(
        self,
        *,
        system: list[dict],
        tools: list[dict],
        messages: list[dict],
    ) -> int | None:
        return None
